from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Clase base para los futuros modelos de la base de datos."""


def get_database() -> Generator[Session, None, None]:
    """Proporciona una sesión y la cierra después de utilizarla."""

    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def check_database_connection() -> bool:
    """Comprueba la comunicación con PostgreSQL."""

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True
