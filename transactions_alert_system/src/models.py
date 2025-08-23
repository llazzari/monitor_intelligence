from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TransactionStatus(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    REVERSED = "reversed"
    REFUNDED = "refunded"
    PROCESSING = "processing"
    BACKEND_REVERSED = "backend_reversed"
    FAILED = "failed"


class AlertLevel(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Transaction(BaseModel):
    time: str = Field(examples=["00h 00"])
    status: TransactionStatus
    count: int


class Anomaly(BaseModel):
    time: str
    status: TransactionStatus
    count: int
    level: AlertLevel
    score: float
    message: str


class AnomalyResponse(BaseModel):
    message: str
    anomalies: List[Anomaly] = []


class TransactionQuery(BaseModel):
    start_hour: Optional[str] = Field(
        None, examples=["00h 00"], pattern=r"^\d{2}h \d{2}$"
    )
    end_hour: Optional[str] = Field(
        None, examples=["23h 59"], pattern=r"^\d{2}h \d{2}$"
    )
    status: Optional[TransactionStatus] = None


class TransactionStats(BaseModel):
    period: str
    total_count: int
    status_breakdown: dict[TransactionStatus, int]
    average_count: float
    max_count: int


class BaselineStats(BaseModel):
    status: TransactionStatus
    mean: float
    std_dev: float
    percentile_95: float
    percentile_99: float
    updated_at: datetime = Field(default_factory=datetime.now)
