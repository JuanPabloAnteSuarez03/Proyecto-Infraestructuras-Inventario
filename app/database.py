"""
Configuración de SQLAlchemy sin Flask.

Expone un engine global, un SessionLocal reutilizable y la Base declarativa.
Incluye handling especial para SQLite (memoria) para que los tests y entornos
ligeros funcionen sin errores de pool.
"""
from collections.abc import Iterator
import os
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# URL de conexión desde variables de entorno
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/inventarios_db",
)


def _build_engine():
    url = make_url(DATABASE_URL)
    engine_kwargs: dict = {"pool_pre_ping": True}

    if url.drivername.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if url.database in (None, "", ":memory:"):
            engine_kwargs["poolclass"] = StaticPool
    else:
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20

    return create_engine(url, **engine_kwargs)


# Crear engine y sessionmaker globales
engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()


def get_db() -> Iterator[Session]:
    """Dependency de FastAPI para obtener sesión de base de datos por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
