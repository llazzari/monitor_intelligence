from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel


class TransactionStatus(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    REVERSED = "reversed"
    REFUNDED = "refunded"
    PROCESSING = "processing"
    BACKEND_REVERSED = "backend_reversed"
    FAILED = "failed"


class TransactionBase(SQLModel):
    time: str = PydanticField(
        examples=["00h 00", "23h 59"]
    )  # in a real app would be a datetime
    status: TransactionStatus
    count: int


class TransactionDB(TransactionBase, table=True):
    __tablename__ = "transactions"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)


class AlertLevel(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AnomalyBase(SQLModel):
    time: str
    status: TransactionStatus
    count: int
    level: AlertLevel
    score: float
    message: str


class AnomalyDB(AnomalyBase, table=True):
    __tablename__ = "anomalies"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)


class AnomalyResponse(BaseModel):
    message: str
    anomalies: list[AnomalyBase] = []


class Stats(SQLModel):
    mean: float
    std: float
    p95: float
    p99: float


class BaselineDB(Stats, table=True):
    __tablename__ = "baselines"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    status: TransactionStatus
    hour: int
    updated_at: datetime = Field(default_factory=datetime.now)


class TransactionQuery(BaseModel):
    start_hour: Optional[str] = PydanticField(
        None, examples=["00h 00"], pattern=r"^\d{2}h \d{2}$"
    )
    end_hour: Optional[str] = PydanticField(
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
    updated_at: datetime = PydanticField(default_factory=datetime.now)
