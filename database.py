from pathlib import Path
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent

if "pytest" in sys.modules:
    DATABASE_FILE = BASE_DIR / 'bloodlink_test.db'
    if DATABASE_FILE.exists():
        DATABASE_FILE.unlink()
else:
    DATABASE_FILE = BASE_DIR / 'bloodlink.db'

DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
