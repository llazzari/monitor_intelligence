from collections import defaultdict

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
        self.baseline_stats: dict[str, Stats] = {}
        self._load_baseline()

    def _get_baseline_by_status(self, df: pd.DataFrame) -> None:
        """Get baseline statistics by transaction status and hour"""
        for status in TransactionStatus:
            status_data = df[df["status"] == status.value]
            if not status_data.empty:
                stats = Stats(
                    mean=float(status_data["count"].mean()),
                    std=float(status_data["count"].std()),
                    p95=float(status_data["count"].quantile(0.95)),
                    p99=float(status_data["count"].quantile(0.99)),
                )
                self.baseline_stats[status.value] = stats

    def _load_baseline(self) -> None:
        """Load baseline data"""
        statement = select(TransactionDB)
        results = self.session.exec(statement).all()
        if not results:
            return

        df = pd.DataFrame([tx.model_dump() for tx in results])

        self._get_baseline_by_status(df)

    def update_baseline(self, historical_data: pd.DataFrame) -> None:
        """Update baseline using historical data"""

        self._get_baseline_by_status(historical_data)
        for status, stats in self.baseline_stats.items():
            self.session.add(
                BaselineDB(**stats.model_dump(), status=TransactionStatus(status))
            )

    def detect_anomalies(
        self, transactions: list[TransactionBase]
    ) -> list[AnomalyBase]:
        """Detect anomalies in transactions"""
        print(f"\nStarting anomaly detection for {len(transactions)} transactions")
        anomalies: list[AnomalyBase] = []

        grouped_data: defaultdict[tuple[str, str], int] = defaultdict(int)
        for tx in transactions:
            grouped_data[(tx.status, tx.time)] += tx.count

        print(f"Grouped data: {dict(grouped_data)}")
        print(f"Available baseline stats: {list(self.baseline_stats.keys())}")

        # Process each group
        for (status, time), count in grouped_data.items():
            print(f"\nProcessing {status} at {time} with count {count}")
            if status not in self.baseline_stats:
                print(f"Skipping {status} - no baseline stats")
                continue

            baseline = self.baseline_stats[status]
            sigma: float = max(1.0, float(baseline.std))
            z_score: float = (count - baseline.mean) / sigma

            # Only check anomalies for bad status transactions
            if status not in BAD_STATUS:
                print(f"Skipping {status} - not in BAD_STATUS {BAD_STATUS}")
                continue

            # Determine anomaly level and message
            level = None
            message = ""

            if count > baseline.p99 or abs(z_score) > 3:
                level = AlertLevel.CRITICAL
                message = (
                    f"Count ({count}) exceeds 99th percentile ({baseline.p99:.2f})"
                    if count > baseline.p99
                    else f"Count ({count}) is more than 3 standard deviations from mean"
                )
            elif count > baseline.p95 or abs(z_score) > 2:
                level = AlertLevel.WARNING
                message = (
                    f"Count ({count}) exceeds 95th percentile ({baseline.p95:.2f})"
                    if count > baseline.p95
                    else f"Count ({count}) is more than 2 standard deviations from mean"
                )

            if level:
                anomalies.append(
                    AnomalyBase(
                        time=time,
                        status=TransactionStatus(status),
                        count=count,
                        level=level,
                        score=float(z_score),
                        message=message,
                    )
                )

        return anomalies
