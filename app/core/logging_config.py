import logging
import os


def setup_logging() -> None:
    """Configura logging simple para toda la app."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
