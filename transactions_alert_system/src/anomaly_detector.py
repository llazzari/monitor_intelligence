from typing import Optional

import numpy as np
import pandas as pd
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
    def __init__(self, session: Session) -> None:
        self.session = session
        self.baseline_stats: dict[int, dict[str, Stats]] = {}
        self._load_baseline()

    def _get_baseline_by_hour_and_status(self, df: pd.DataFrame) -> None:
        """Get baseline statistics by transaction status and hour"""
        df["hour"] = df["time"].str.extract(r"(\d{2})h").astype(int)
        df_total_count = df.groupby("hour")["count"].sum()
        for hour in df["hour"].unique():
            hour = int(hour)
            self.baseline_stats[hour] = {}
            total_count = int(df_total_count.iloc[hour])
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
                        total_count=total_count,
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

    def update_baseline(self, historical_data: pd.DataFrame) -> None:
        """Update baseline using historical data"""

        self._get_baseline_by_hour_and_status(historical_data)
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
        """Detect anomalies in transactions"""
        print(f"\nStarting anomaly detection for {len(transactions)} transactions")
        anomalies: list[AnomalyBase] = []

        for tx in transactions:
            # Only check anomalies for bad status transactions
            if tx.status.value not in BAD_STATUS:
                print(f"Skipping {tx.status.value} - not in BAD_STATUS {BAD_STATUS}")
                continue

            hour = int(tx.time.split("h")[0])
            baseline = self.baseline_stats[hour][tx.status]
            sigma = 1.4826 * baseline.mad if baseline.mad > 0 else baseline.std
            sigma: float = max(1.0, sigma)

            z_score: float = (tx.count - baseline.mean) / sigma

            level: Optional[AlertLevel] = None
            message: str = ""

            if tx.count > baseline.p99 and abs(z_score) > 3:
                level = AlertLevel.CRITICAL
                message = f"Count ({tx.count}) exceeds 99th percentile ({baseline.p99:.2f}) and is more than 3 standard deviations from mean"
            elif tx.count > baseline.p95 and abs(z_score) > 2:
                level = AlertLevel.WARNING
                message = f"Count ({tx.count}) exceeds 95th percentile ({baseline.p95:.2f}) and is more than 2 standard deviations from mean"

            if level:
                anomalies.append(
                    AnomalyBase(
                        time=tx.time,
                        status=tx.status,
                        count=tx.count,
                        level=level,
                        score=float(z_score),
                        message=message,
                    )
                )

        print(f"{len(anomalies)} anomalies have been detected.")
        df_anom = pd.DataFrame([a.model_dump() for a in anomalies])
        df_anom.to_csv("./transactions_alert_system/data/anoms_2.csv", index=False)
        return anomalies
