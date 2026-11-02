import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger("smartbin.database")

db_url = settings.DATABASE_URL

# Render compatibility: Render sets DATABASE_URL as postgres://, SQLAlchemy requires postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Robust engine initialization with automatic SQLite fallback if PostgreSQL is not available
try:
    if "postgresql" in db_url:
        connect_args = {"connect_timeout": 5}
        # If connecting to cloud/Render, require SSL
        if "render.com" in db_url:
            connect_args["sslmode"] = "require"
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            connect_args=connect_args
        )
        # Test connection
        with engine.connect() as conn:
            pass
        logger.info(f"Connected to PostgreSQL database: {db_url}")
    else:
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
except Exception as e:
    logger.warning(f"Could not connect to configured database ({db_url}): {e}. Falling back to SQLite local database.")
    fallback_url = "sqlite:///./smartbin.db"
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)

