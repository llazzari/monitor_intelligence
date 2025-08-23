import pathlib
from contextlib import asynccontextmanager
from typing import Dict, List

import pandas as pd
import plotly.express as px
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from .anomaly_detector import AnomalyDetector
from .db_models import TransactionDB
from .models import Anomaly, AnomalyResponse, Transaction, TransactionQuery
from .notification import NotificationService
from .session import engine, get_session, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Initialize baseline on startup using transactions_1.csv data
    with Session(engine) as session:
        detector = AnomalyDetector(session)
        historical_data = pd.read_csv(
            pathlib.Path.cwd()
            / "transactions_alert_system"
            / "data"
            / "transactions_1.csv"
        )
        detector.update_baseline(historical_data)
    yield


app = FastAPI(lifespan=lifespan)
notification_service = NotificationService()


@app.post("/transactions", response_model=AnomalyResponse)
async def process_transactions(
    transactions: list[Transaction], session: Session = Depends(get_session)
):
    # Save transactions to database
    for tx in transactions:
        db_tx = TransactionDB(time=tx.time, status=tx.status, count=tx.count)
        session.add(db_tx)
    session.commit()

    # Detect anomalies
    detector = AnomalyDetector(session)
    anomalies: List[Dict[str, float | str]] = detector.detect_anomalies(transactions)

    # Send notifications if there are anomalies
    if anomalies:
        notification_service.send_alert(anomalies)

    return AnomalyResponse(
        message="Transactions processed successfully",
        anomalies=[Anomaly(**anomaly) for anomaly in anomalies],
    )


@app.post("/query")
async def query_transactions(
    query: TransactionQuery, session: Session = Depends(get_session)
) -> List[Transaction]:
    # Build query for transactions
    statement = select(TransactionDB)

    if query.start_hour:
        statement = statement.where(TransactionDB.time >= query.start_hour)
    if query.end_hour:
        statement = statement.where(TransactionDB.time <= query.end_hour)
    if query.status:
        statement = statement.where(TransactionDB.status == query.status)

    transactions = session.exec(statement).all()

    # Convert DB models to Transaction models and return
    return [
        Transaction(time=tx.time, status=tx.status, count=tx.count)
        for tx in transactions
    ]


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(session: Session = Depends(get_session)):
    # Get all transactions and process them
    statement = select(TransactionDB)
    transactions = session.exec(statement).all()

    if not transactions:
        return HTMLResponse(content="<h2>No transactions found</h2>", status_code=404)

    # Convert to DataFrame
    df = pd.DataFrame(
        [
            {"time": tx.time, "status": tx.status, "count": tx.count}
            for tx in transactions
        ]
    )

    # Extract hour for sorting and convert to numeric for proper ordering
    df["hour"] = df["time"].str.extract(r"(\d{2})h").astype(int)
    df = df.sort_values("hour")

    # Create transaction volume plot
    fig1 = px.line(
        df,
        x="time",
        y="count",
        color="status",
        title="Transaction Volume Over Time by Status",
    )
    fig1.update_layout(
        xaxis_title="Hour",
        yaxis_title="Transaction Count",
        height=400,
        xaxis={"categoryorder": "array", "categoryarray": sorted(df["time"].unique())},
    )

    # Create status breakdown plot
    status_totals = df.groupby("status")["count"].sum().reset_index()
    fig2 = px.bar(
        status_totals,
        x="status",
        y="count",
        title="Total Transactions by Status",
    )
    fig2.update_layout(xaxis_title="Status", yaxis_title="Total Count", height=400)

    # Get anomaly statistics
    detector = AnomalyDetector(session)
    anomalies = detector.detect_anomalies(
        [
            Transaction(time=row["time"], status=row["status"], count=row["count"])
            for _, row in df.iterrows()
        ]
    )

    critical_count = len([a for a in anomalies if a["level"] == "CRITICAL"])
    warning_count = len([a for a in anomalies if a["level"] == "WARNING"])

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
                        <h3>Last 24 Hours</h3>
                        <p>Total Transactions: {df["count"].sum()}</p>
                    </div>
                    <div class="stat-box">
                        <h3>Anomalies</h3>
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
