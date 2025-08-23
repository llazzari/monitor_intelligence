from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class TransactionDB(SQLModel, table=True):
    __tablename__ = "transactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    time: str  # in a real application, this would be a datetime
    status: str
    count: int
    created_at: datetime = Field(default_factory=datetime.now)


class AnomalyDB(SQLModel, table=True):
    __tablename__ = "anomalies"

    id: Optional[int] = Field(default=None, primary_key=True)
    time: str
    status: str
    count: int
    level: str  # WARNING or CRITICAL
    score: float  # Z-score or anomaly score
    created_at: datetime = Field(default_factory=datetime.now)


class BaselineDB(SQLModel, table=True):
    __tablename__ = "baselines"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: str
    mean: float
    std: float
    p95: float
    p99: float
    updated_at: datetime = Field(default_factory=datetime.now)
