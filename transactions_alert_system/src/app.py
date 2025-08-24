import pathlib
from contextlib import asynccontextmanager

import pandas as pd
import plotly.express as px
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from .anomaly_detector import AnomalyDetector
from .models import (
    AnomalyDB,
    AnomalyResponse,
    TransactionBase,
    TransactionDB,
    TransactionQuery,
    TransactionStatus,
)
from .notification import NotificationService
from .session import engine, get_session, init_db

DATA_PATH = pathlib.Path.cwd() / "transactions_alert_system" / "data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Initialize baseline on startup using transactions_1.csv data
    # Insert transactions_2.csv data into transactions.db (if it is not there yet)
    with Session(engine) as session:
        global detector
        detector = AnomalyDetector(session)
        historical_data = pd.read_csv(DATA_PATH / "transactions_1.csv")  # type: ignore
        detector.update_baseline(historical_data)

        # Check if transactions_2.csv data is already in the database
        existing_data = session.exec(select(TransactionDB)).all()
        if not existing_data:
            new_data = pd.read_csv(DATA_PATH / "transactions_2.csv")  # type: ignore
            new_transactions = [
                TransactionBase(**transaction)  # type: ignore
                for transaction in new_data.to_dict("records")  # type: ignore
            ]

            anomalies: list[AnomalyBase] = detector.detect_anomalies(new_transactions)

            for tx in new_transactions:
                db_tx = TransactionDB(**tx.model_dump())
                session.add(db_tx)

            for anomaly in anomalies:
                db_anomaly = AnomalyDB(**anomaly.model_dump())
                session.add(db_anomaly)

            session.commit()
    yield


app = FastAPI(lifespan=lifespan)
notification_service = NotificationService()


@app.post("/transactions", response_model=AnomalyResponse)
async def process_transactions(
    transactions: list[TransactionBase], session: Session = Depends(get_session)
):
    for tx in transactions:
        db_tx = TransactionDB(**tx.model_dump())
        session.add(db_tx)

    detector = AnomalyDetector(session)
    anomalies = detector.detect_anomalies(transactions)

    if anomalies:
        for anomaly in anomalies:
            db_anomaly = AnomalyDB(**anomaly.model_dump())
            session.add(db_anomaly)
        notification_service.send_alert(anomalies)

    detector.update_baseline(pd.DataFrame([tx.model_dump() for tx in transactions]))

    session.commit()

    return AnomalyResponse(
        message="Transactions processed successfully",
        anomalies=anomalies,
    )


@app.post("/query", response_model=list[TransactionBase])
async def query_transactions(
    query: TransactionQuery, session: Session = Depends(get_session)
) -> list[TransactionBase]:
    statement = select(TransactionDB)

    if query.start_hour:
        statement = statement.where(TransactionDB.time >= query.start_hour)
    if query.end_hour:
        statement = statement.where(TransactionDB.time <= query.end_hour)
    if query.status:
        statement = statement.where(TransactionDB.status == query.status)

    transactions = session.exec(statement).all()

    return [
        TransactionBase(
            time=tx.time, status=TransactionStatus(tx.status), count=tx.count
        )
        for tx in transactions
    ]


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(session: Session = Depends(get_session)):
    # get highest hour in the database to present the newest data
    statement = select(TransactionDB).order_by(TransactionDB.time.desc()).limit(1)
    result: TransactionDB | None = session.exec(statement).first()
    hour = int(result.time.split("h")[0]) if result else 16

    statement = select(TransactionDB).where(
        TransactionDB.time >= f"{hour}h 00", TransactionDB.time <= f"{hour}h 59"
    )
    transactions = session.exec(statement).all()

    print(f"\nFound {len(transactions)} transactions for the last hour")
    print(
        "Sample transactions:",
        [f"{tx.time}: {tx.status}={tx.count}" for tx in transactions[:5]],
    )

    if not transactions:
        return HTMLResponse(
            content="<h2>No transactions found for the last hour</h2>", status_code=404
        )

    df = pd.DataFrame([tx.model_dump() for tx in transactions])

    # Extract hour for sorting and convert to numeric for proper ordering
    df["hour"] = df["time"].str.extract(r"(\d{2})h").astype(int)
    df = df.sort_values("hour")

    # Get anomalies for the last hour
    anomaly_statement = select(AnomalyDB).where(
        AnomalyDB.time >= f"{hour}h 00", AnomalyDB.time <= f"{hour}h 59"
    )
    anomalies_db = session.exec(anomaly_statement).all()
    print(f"\nFound {len(anomalies_db)} anomalies in DB for the last hour")
    print(
        "Sample anomalies:",
        [f"{a.time}: {a.status}={a.count} ({a.level})" for a in anomalies_db[:5]],
    )

    # Create transaction volume plot
    fig1 = px.line(  # type: ignore
        df,
        x="time",
        y="count",
        color="status",
        title="Transaction Volume Over Time by Status (⚠️ marks anomalies)",
        color_discrete_map={
            "approved": "#3A8309",
            "declined": "#FF0000",
            "failed": "#D10000",
            "reversed": "#FF7276",
            "backend_reversed": "#FFB3B3",
            "refunded": "blue",
        },
        # markers=True,
    )

    print("Anomalies found in DB:", len(anomalies_db))
    # Add special markers for anomalies
    for status in df["status"].unique():
        # Filter anomalies for this status and print debug info
        status_anomalies = [a for a in anomalies_db if a.status == status]
        print(f"Anomalies for status {status}:", len(status_anomalies))

        if status_anomalies:
            print(f"Adding markers for {status} anomalies:")
            for anomaly in status_anomalies:
                print(
                    f"  - time: {anomaly.time}, count: {anomaly.count}, level: {anomaly.level}"
                )

            fig1.add_scatter(  # type: ignore
                x=[a.time for a in status_anomalies],
                y=[a.count for a in status_anomalies],
                mode="markers",
                marker=dict(
                    symbol="star",
                    size=12,
                    line=dict(width=2, color="black"),
                    color="red",  # Make anomalies stand out
                ),
                name=f"{status} (Anomaly)",
                showlegend=True,  # Show in legend to distinguish anomalies
            )

    fig1.update_layout(  # type: ignore
        xaxis_title="Hour",
        yaxis_title="Transaction Count",
        height=400,
        xaxis={"categoryorder": "array", "categoryarray": sorted(df["time"].unique())},
    )

    # Create status breakdown plot
    status_totals = df.groupby("status")["count"].sum().reset_index()  # type: ignore
    fig2 = px.bar(  # type: ignore
        status_totals,
        x="status",
        y="count",
        title="Total Transactions by Status",
        text="count",
    )
    fig2.update_layout(xaxis_title="Status", yaxis_title="Total Count", height=400)  # type: ignore

    # Get anomaly statistics
    detector = AnomalyDetector(session)
    anomalies = detector.detect_anomalies(
        [
            TransactionBase(time=row["time"], status=row["status"], count=row["count"])
            for _, row in df.iterrows()
        ]
    )

    critical_count = len([a for a in anomalies if a.level == "CRITICAL"])
    warning_count = len([a for a in anomalies if a.level == "WARNING"])

    dashboard_html = f"""
    <html>
        <head>
            <title>Transaction Monitoring Dashboard</title>
            <style>
                .container {{ 
                    max-width: 1200px; 
                    margin: 0 auto; 
                    padding: 20px;
                }}
                .plot-container {{ 
                    margin-bottom: 30px; 
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .stats-container {{
                    display: flex;
                    justify-content: space-around;
                    margin-bottom: 30px;
                }}
                .stat-box {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .critical {{
                    color: #dc3545;
                }}
                .warning {{
                    color: #ffc107;
                }}
                h1 {{ 
                    text-align: center; 
                    color: #333;
                    margin-bottom: 30px;
                }}
                body {{
                    background: #f5f5f5;
                    font-family: Arial, sans-serif;
                }}
            </style>
            <meta http-equiv="refresh" content="60">
        </head>
        <body>
            <div class="container">
                <h1>Transaction Monitoring Dashboard</h1>
                
                <div class="stats-container">
                    <div class="stat-box">
                        <h3>Chosen Hour ({hour}h)</h3>
                        <p>Total Transactions: {df["count"].sum()}</p>
                    </div>
                    <div class="stat-box">
                        <h3>Anomalies in Last Hour</h3>
                        <p class="critical">Critical: {critical_count}</p>
                        <p class="warning">Warnings: {warning_count}</p>
                    </div>
                </div>
                
                <div class="plot-container">
                    {fig1.to_html(full_html=False)} 
                </div>
                <div class="plot-container">
                    {fig2.to_html(full_html=False)}
                </div>
            </div>
        </body>
    </html>
    """

    return dashboard_html
