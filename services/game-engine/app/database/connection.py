"""
Database Connection for PostgreSQL
Provides session management for SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
import os

from ..core.logging import get_logger
from .models import Base

logger = get_logger(__name__)


class DatabaseConnection:
    """PostgreSQL database connection manager"""

    def __init__(self):
        self.database_url = os.getenv(
            'POSTGRES_URL',
            'postgresql://skillforge_user:password@postgres:5432/skillforge'
        )

        # Create engine with connection pooling
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set to True for SQL debugging
        )

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info("database_initialized", url=self.database_url.split('@')[1])

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions

        Usage:
            with db.get_session() as session:
                character = session.query(Character).filter_by(character_id=id).first()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("database_session_error", error=str(e))
            raise
        finally:
            session.close()

    def get_db(self) -> Session:
        """
        Get database session (for dependency injection)

        Usage in FastAPI:
            @app.get("/endpoint")
            def endpoint(db: Session = Depends(get_db)):
                ...
        """
        db = self.SessionLocal()
        try:
            return db
        except Exception as e:
            db.close()
            raise

    def close(self):
        """Close all database connections"""
        self.engine.dispose()
        logger.info("database_connections_closed")

    def verify_connection(self) -> bool:
        """Verify database connection is working"""
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            logger.info("database_connection_verified")
            return True
        except Exception as e:
            logger.error("database_connection_failed", error=str(e))
            return False


# Global database instance
db_connection = DatabaseConnection()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions

    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            character = db.query(Character).filter_by(character_id=id).first()
    """
    db = db_connection.SessionLocal()
    try:
        yield db
    finally:
        db.close()
