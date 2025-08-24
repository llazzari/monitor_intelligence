from typing import Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlmodel import Session, select

from .models import (
    AlertLevel,
    AnomalyBase,
    BaselineDB,
    Stats,
    TransactionBase,
    TransactionDB,
    TransactionStatus,
)

BAD_STATUS: list[str] = ["failed", "denied", "reversed", "backend_reversed"]


class AnomalyDetector:
    def __init__(
        self, session: Session, contamination: float = 0.49, random_state: int = 42
    ) -> None:
        self.session = session
        self.baseline_stats: dict[int, dict[str, Stats]] = {}
        self.baseline_features_df: Optional[pd.DataFrame] = None

        self.isolation_forest = IsolationForest(
            contamination=contamination, random_state=random_state
        )

        self.feature_columns = [
            "total_count",
            "bad_count",
            "bad_rate",
            "delta_total",
            "delta_bad_rate",
        ]
        self._load_baseline()
        self._train_isolation_forest()

    def _extract_hour_from_time(self, time_str: str) -> int:
        """Extract hour from time string (e.g., '00h 00' -> 0)"""
        return int(time_str.split("h")[0])

    def _get_baseline_by_hour_and_status(self, df: pd.DataFrame) -> None:
        """Get baseline statistics by transaction status and hour"""
        df["hour"] = df["time"].apply(self._extract_hour_from_time)
        for hour in df["hour"].unique():
            hour = int(hour)
            self.baseline_stats[hour] = {}
            for status in TransactionStatus:
                status_data = df[df["status"] == status.value]
                if not status_data.empty:
                    stats = Stats(
                        mean=float(status_data["count"].mean()),
                        std=float(status_data["count"].std())
                        if not np.isnan(status_data["count"].std())
                        else 1.0,
                        mad=float(status_data["count"].median()),
                        p95=float(status_data["count"].quantile(0.95)),
                        p99=float(status_data["count"].quantile(0.99)),
                    )
                    self.baseline_stats[hour][status.value] = stats

    def _load_baseline(self) -> None:
        """Load baseline data"""
        statement = select(TransactionDB)
        results = self.session.exec(statement).all()
        if not results:
            return

        df = pd.DataFrame([tx.model_dump() for tx in results])
        self._get_baseline_by_hour_and_status(df)

        # Store baseline features for isolation forest training
        self.baseline_features_df = self._prepare_features_dataframe(df)

    def _train_isolation_forest(self) -> None:
        """Train isolation forest on baseline data"""
        if (
            self.baseline_features_df is not None
            and not self.baseline_features_df.empty
        ):
            # Select features for training
            X = self.baseline_features_df[self.feature_columns].fillna(0)

            # Only train if we have sufficient data
            if len(X) > 10:  # Minimum data points for meaningful training
                self.isolation_forest.fit(X)
                print(f"Isolation Forest trained on {len(X)} baseline data points")
            else:
                print("Insufficient baseline data for isolation forest training")

    def _prepare_features_dataframe(
        self, transactions: list[TransactionBase] | pd.DataFrame
    ) -> pd.DataFrame:
        """Prepare features dataframe for isolation forest analysis"""
        # Convert to DataFrame if it's a list
        if isinstance(transactions, list):
            df = pd.DataFrame([tx.model_dump() for tx in transactions])
        else:
            df = transactions.copy()

        # Pivot data by time and status
        df_pivot = df.pivot_table(
            index="time", columns="status", values="count", fill_value=0
        ).reset_index()

        # Calculate features
        df_pivot["total_count"] = df_pivot.drop(columns=["time"]).sum(axis=1)

        # Handle bad status columns safely
        bad_status_cols = [col for col in BAD_STATUS if col in df_pivot.columns]
        if bad_status_cols:
            df_pivot["bad_count"] = df_pivot[bad_status_cols].sum(axis=1)
        else:
            df_pivot["bad_count"] = 0

        df_pivot["bad_rate"] = df_pivot["bad_count"] / df_pivot["total_count"].replace(
            0, 1
        )

        # Sort by time for proper rolling calculations
        df_pivot = df_pivot.sort_values("time").reset_index(drop=True)

        window = 60  # minutes
        df_pivot["rolling_total_mean"] = (
            df_pivot["total_count"].rolling(window, min_periods=1).mean()
        )
        df_pivot["rolling_bad_rate_mean"] = (
            df_pivot["bad_rate"].rolling(window, min_periods=1).mean()
        )

        df_pivot["delta_total"] = (
            df_pivot["total_count"] - df_pivot["rolling_total_mean"]
        )
        df_pivot["delta_bad_rate"] = (
            df_pivot["bad_rate"] - df_pivot["rolling_bad_rate_mean"]
        )

        return df_pivot

    def _predict_with_isolation_forest(self, features_df: pd.DataFrame) -> np.ndarray:
        """Use pre-trained isolation forest to predict anomalies"""
        X = features_df[self.feature_columns].fillna(0)

        return self.isolation_forest.predict(X)

    def _calculate_z_score(self, tx: TransactionBase) -> Tuple[float, float, str]:
        """Calculate z-score for a transaction using baseline statistics"""
        try:
            hour = self._extract_hour_from_time(tx.time)

            # Check if baseline exists for this hour and status
            if (
                hour not in self.baseline_stats
                or tx.status.value not in self.baseline_stats[hour]
            ):
                return 0.0, 0.0, "No baseline data available"

            baseline = self.baseline_stats[hour][tx.status.value]

            # Use MAD (Median Absolute Deviation) for robust statistics
            sigma = 1.4826 * baseline.mad if baseline.mad > 0 else baseline.std
            sigma = max(1.0, sigma)  # Ensure minimum sigma

            z_score = (tx.count - baseline.mean) / sigma

            return z_score, sigma, "Z-score calculated successfully"

        except Exception as e:
            return 0.0, 0.0, f"Error calculating z-score: {str(e)}"

    def _determine_alert_level(
        self, tx: TransactionBase, z_score: float, isolation_score: float
    ) -> Tuple[Optional[AlertLevel], str]:
        """Determine alert level based on z-score and isolation forest results"""
        try:
            hour = self._extract_hour_from_time(tx.time)

            if (
                hour not in self.baseline_stats
                or tx.status.value not in self.baseline_stats[hour]
            ):
                return None, "No baseline data available"

            baseline = self.baseline_stats[hour][tx.status.value]

            # Determine alert level based on combined analysis
            if (tx.count > baseline.p99 and abs(z_score) > 3) and isolation_score == -1:
                return AlertLevel.CRITICAL, (
                    f"CRITICAL: Count ({tx.count}) exceeds 99th percentile ({baseline.p99:.2f}) "
                    f"and z-score ({z_score:.2f}) > 3, isolation forest: {'anomaly'}"
                )
            elif (
                tx.count > baseline.p95 and abs(z_score) > 2
            ) and isolation_score == -1:
                return AlertLevel.WARNING, (
                    f"WARNING: Count ({tx.count}) exceeds 95th percentile ({baseline.p95:.2f}) "
                    f"and z-score ({z_score:.2f}) > 2, isolation forest: {'anomaly'}"
                )

            return None, "No alert level determined"

        except Exception as e:
            return None, f"Error determining alert level: {str(e)}"

    def _analyze_transaction(
        self,
        tx: TransactionBase,
        features_df: pd.DataFrame,
        isolation_predictions: np.ndarray,
    ) -> Optional[AnomalyBase]:
        """Analyze a single transaction for anomalies"""
        # Only check anomalies for bad status transactions
        if tx.status.value not in BAD_STATUS:
            return None

        try:
            # Find the row in features_df that corresponds to this transaction
            tx_row = features_df[features_df["time"] == tx.time]
            if tx_row.empty:
                return None

            tx_index = tx_row.index[0]
            isolation_score = float(isolation_predictions[tx_index])

            # Calculate z-score
            z_score, sigma, z_score_msg = self._calculate_z_score(tx)

            # Determine alert level
            level, message = self._determine_alert_level(tx, z_score, isolation_score)
            print(message)
            if level:
                return AnomalyBase(
                    time=tx.time,
                    status=tx.status,
                    count=tx.count,
                    level=level,
                    score=float(z_score),
                    message=message,
                )

            return None

        except Exception as e:
            print(f"Error analyzing transaction {tx.time}: {str(e)}")
            return None

    def update_baseline(self, historical_data: pd.DataFrame) -> None:
        """Update baseline using historical data"""
        self._get_baseline_by_hour_and_status(historical_data)

        # Retrain isolation forest with updated baseline
        self.baseline_features_df = self._prepare_features_dataframe(historical_data)
        self._train_isolation_forest()

        # Save to database
        for hour, baseline in self.baseline_stats.items():
            for status, stats in baseline.items():
                self.session.add(
                    BaselineDB(
                        **stats.model_dump(),
                        status=TransactionStatus(status),
                        hour=hour,
                    )
                )

    def detect_anomalies(
        self, transactions: list[TransactionBase]
    ) -> list[AnomalyBase]:
        """Detect anomalies using both z-score analysis and isolation forest"""
        print(
            f"\nStarting comprehensive anomaly detection for {len(transactions)} transactions"
        )

        if not transactions:
            return []

        # Check if isolation forest is trained
        if (
            not hasattr(self.isolation_forest, "estimators_")
            or self.isolation_forest.estimators_ is None
        ):
            print("Warning: Isolation Forest not trained. Using only z-score analysis.")
            # Fall back to z-score only analysis
            anomalies: list[AnomalyBase] = []
            for tx in transactions:
                if tx.status.value in BAD_STATUS:
                    z_score, sigma, z_score_msg = self._calculate_z_score(tx)
                    if abs(z_score) > 3:  # Simple threshold-based alert
                        anomalies.append(
                            AnomalyBase(
                                time=tx.time,
                                status=tx.status,
                                count=tx.count,
                                level=AlertLevel.WARNING,
                                score=float(z_score),
                                message=f"Z-score based alert: {z_score:.2f}",
                            )
                        )
            return anomalies

        # Prepare features for new transactions
        features_df = self._prepare_features_dataframe(transactions)

        # Use pre-trained isolation forest for predictions (NO RETRAINING)
        isolation_predictions = self._predict_with_isolation_forest(features_df)

        # Analyze each transaction
        anomalies: list[AnomalyBase] = []

        for tx in transactions:
            anomaly = self._analyze_transaction(tx, features_df, isolation_predictions)
            if anomaly:
                anomalies.append(anomaly)

        print(f"{len(anomalies)} anomalies detected using combined analysis")

        # Save anomalies to CSV for debugging
        if anomalies:
            df_anom = pd.DataFrame([a.model_dump() for a in anomalies])
            df_anom.to_csv(
                "./transactions_alert_system/data/anomalies_detected.csv", index=False
            )

        return anomalies
