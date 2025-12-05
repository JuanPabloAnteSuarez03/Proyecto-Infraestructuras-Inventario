"""
Cliente Redis compartido para configuración y caché ligera.
Se usa para almacenar parámetros dinámicos (ej. FABRICA_BASE_URL) accesibles por API y worker.
"""
import os
import redis

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Devuelve un cliente Redis singleton usando REDIS_URL (por defecto redis://redis:6379/0)."""
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        _redis_client = redis.from_url(url)
    return _redis_client
