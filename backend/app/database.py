import os
import stat
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _set_db_permissions(db_path: str) -> None:
    """Set database file to owner-read/write only (0600)."""
    p = Path(db_path)
    if p.exists():
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)


def _configure_sqlite(connection, _connection_record):  # noqa: ANN001
    """Enable WAL mode and foreign keys on every new SQLite connection.

    This listener receives the raw sqlite3.Connection, not an SQLAlchemy
    connection, so we use plain string execute() calls directly.
    """
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA synchronous=NORMAL")


def create_db_engine():
    db_url = settings.db_url
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    event.listen(engine, "connect", _configure_sqlite)
    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a DB session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables and set secure file permissions."""
    Base.metadata.create_all(bind=engine)
    db_file = settings.db_path
    _set_db_permissions(db_file)
