from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# Create data directory if it doesn't exist
DB_DIR = Path.cwd() / "transactions_alert_system" / "data"
DB_DIR.mkdir(exist_ok=True)

SQLITE_URL = f"sqlite:///{DB_DIR}/transactions.db"
engine = create_engine(SQLITE_URL)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
