from typing import Dict, List

import pandas as pd
from sqlmodel import Session, select

from .db_models import TransactionDB
from .models import Transaction, TransactionStatus


class AnomalyDetector:
    def __init__(self, session: Session):
        self.session = session
        self.baseline_stats = {}
        self._load_baseline()

    def _load_baseline(self) -> None:
        """Load baseline data"""
        statement = select(TransactionDB)
        results = self.session.exec(statement).all()
        if not results:
            return

        df = pd.DataFrame(
            [
                {"time": tx.time, "status": tx.status, "count": tx.count}
                for tx in results
            ]
        )

        # Calculate baseline statistics for each status
        for status in TransactionStatus:
            status_data = df[df["status"] == status.value]
            if not status_data.empty:
                self.baseline_stats[status.value] = {
                    "mean": float(status_data["count"].mean()),
                    "std": float(status_data["count"].std()),
                    "p95": float(status_data["count"].quantile(0.95)),
                    "p99": float(status_data["count"].quantile(0.99)),
                }

    def update_baseline(self, historical_data: pd.DataFrame):
        """Update baseline using historical data"""
        for status in TransactionStatus:
            status_data = historical_data[historical_data["status"] == status.value]
            if not status_data.empty:
                self.baseline_stats[status.value] = {
                    "mean": float(status_data["count"].mean()),
                    "std": float(status_data["count"].std()),
                    "p95": float(status_data["count"].quantile(0.95)),
                    "p99": float(status_data["count"].quantile(0.99)),
                }

    def detect_anomalies(
        self, transactions: List[Transaction]
    ) -> List[Dict[str, str | float]]:
        """Detect anomalies in transactions"""
        anomalies: List[Dict[str, str | float]] = []

        # Group transactions by hour and status
        df = pd.DataFrame([tx.model_dump() for tx in transactions])
        grouped = df.groupby(["status", "time"])["count"].sum().reset_index()

        for _, row in grouped.iterrows():
            status = row["status"]
            count = row["count"]
            time = row["time"]

            if status not in self.baseline_stats:
                continue

            baseline = self.baseline_stats[status]

            # selects the maximum between 1 and the real standard deviation to avoid small values
            sigma: float = max(1.0, float(baseline["std"]))
            # Calculate z-score
            z_score: float = (count - baseline["mean"]) / sigma

            # Check for anomalies based on status
            is_critical = False
            is_warning = False
            message = ""

            if status in ["failed", "denied", "reversed"]:
                if count > baseline["p99"]:
                    is_critical = True
                    message = f"Count ({count}) exceeds 99th percentile ({baseline['p99']:.2f})"
                elif count > baseline["p95"]:
                    is_warning = True
                    message = f"Count ({count}) exceeds 95th percentile ({baseline['p95']:.2f})"
                elif abs(z_score) > 3:
                    is_critical = True
                    message = (
                        f"Count ({count}) is more than 3 standard deviations from mean"
                    )
                elif abs(z_score) > 2:
                    is_warning = True
                    message = (
                        f"Count ({count}) is more than 2 standard deviations from mean"
                    )

            if is_critical or is_warning:
                anomalies.append(
                    {
                        "time": time,
                        "status": status,
                        "count": count,
                        "level": "CRITICAL" if is_critical else "WARNING",
                        "score": float(z_score),
                        "message": message,
                    }
                )

        return anomalies
