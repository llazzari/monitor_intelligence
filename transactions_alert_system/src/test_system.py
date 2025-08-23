import asyncio
import pathlib

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from .app import app
from .models import Transaction

client = TestClient(app)


def load_test_data() -> list[list[Transaction]]:
    data_path = (
        pathlib.Path.cwd() / "transactions_alert_system" / "data" / "transactions_2.csv"
    )
    df = pd.read_csv(data_path)

    # Convert data to Transaction objects
    transactions = [
        Transaction(time=row["time"], status=row["status"], count=row["count"])
        for _, row in df.iterrows()
    ]

    # Group transactions by time for batch processing
    batches: dict[str, list[Transaction]] = {}
    for tx in transactions:
        if tx.time not in batches:
            batches[tx.time] = []
        batches[tx.time].append(tx)

    return list(batches.values())


@pytest.mark.asyncio
async def test_alert_system():
    # Load test data in batches
    transaction_batches = load_test_data()

    print("\nStarting Alert System Test...")

    anomaly_counter: int = 0
    for batch in transaction_batches:
        # Send batch of transactions
        response = client.post("/transactions", json=[tx.model_dump() for tx in batch])
        assert response.status_code == 200

        result = response.json()
        if result["anomalies"]:
            print(f"\nAnomalies detected at {batch[0].time}:")
            for anomaly in result["anomalies"]:
                print(
                    f"- {anomaly['level']}: {anomaly['status']} "
                    f"(count: {anomaly['count']}, score: {anomaly['score']:.2f})"
                )
        if anomaly_counter > 10:
            break  # to avoid overflooding the mailbox
        # Small delay to simulate real-time data
        await asyncio.sleep(0.1)
        anomaly_counter += 1

    print("\nTest completed!")
