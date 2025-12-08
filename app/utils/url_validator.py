"""
URL validation utilities for external service configuration.
Validates URLs for fabrication service and other external integrations.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse
from typing import Optional


class URLValidationError(Exception):
    """Raised when a URL fails validation."""

    def __init__(self, message: str, url: str, details: dict | None = None):
        self.message = message
        self.url = url
        self.details = details or {}
        super().__init__(message)


class FabricationURLValidator:
    """Validator for external fabrication service URLs."""

    # Valid schemes
    VALID_SCHEMES = {"http", "https"}

    # Common Docker/local hostnames
    DOCKER_HOSTNAMES = {
        "host.docker.internal",
        "localhost",
        "127.0.0.1",
        "0.0.0.0"
    }

    # Regex patterns for malformed URLs (checked before parsing)
    MALFORMED_PATTERNS = [
        (r"://\s+", "Espacio después del separador '://' no permitido"),
        (r"\s+:", "Espacio antes del separador de puerto no permitido"),
    ]

    # Patterns for port in path (checked after parsing, only against path component)
    PORT_IN_PATH_PATTERNS = [
        (r"^/localhost:\d+", "Puerto en la ruta en lugar del hostname (encontrado /localhost:)"),
        (r"^/127\.0\.0\.1:\d+", "Puerto en la ruta en lugar del hostname (encontrado /127.0.0.1:)"),
        (r"^/host\.docker\.internal:\d+", "Puerto en la ruta en lugar del hostname (encontrado /host.docker.internal:)"),
        (r"/[^/]+:\d+", "Número de puerto en la ruta en lugar del hostname"),
    ]

    @classmethod
    def validate(cls, url: str, allow_empty: bool = False) -> str:
        """
        Validate and normalize a fabrication service URL.

        Args:
            url: The URL to validate
            allow_empty: If True, empty strings are valid and returned as-is

        Returns:
            Normalized URL (stripped of trailing slashes)

        Raises:
            URLValidationError: If URL is invalid
        """
        # Handle empty/None
        if not url or not url.strip():
            if allow_empty:
                return ""
            raise URLValidationError(
                "La URL no puede estar vacía",
                url="",
                details={"hint": "Proporcione una URL válida como http://host.docker.internal:8555"}
            )

        url = url.strip()

        # Check for malformed patterns
        for pattern, description in cls.MALFORMED_PATTERNS:
            if re.search(pattern, url):
                raise URLValidationError(
                    f"URL malformada: {description}",
                    url=url,
                    details={
                        "pattern_matched": pattern,
                        "issue": description,
                        "examples": cls._get_examples()
                    }
                )

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise URLValidationError(
                f"No se puede parsear la URL: {str(e)}",
                url=url,
                details={"parse_error": str(e)}
            )

        # Validate scheme
        if not parsed.scheme:
            raise URLValidationError(
                "Falta el esquema de la URL (http:// o https://)",
                url=url,
                details={
                    "hint": f"¿Quiso decir: http://{url}?",
                    "examples": cls._get_examples()
                }
            )

        if parsed.scheme not in cls.VALID_SCHEMES:
            raise URLValidationError(
                f"Esquema de URL inválido '{parsed.scheme}'",
                url=url,
                details={
                    "valid_schemes": list(cls.VALID_SCHEMES),
                    "examples": cls._get_examples()
                }
            )

        # Validate hostname
        if not parsed.netloc:
            raise URLValidationError(
                "Falta el hostname",
                url=url,
                details={
                    "hint": "La URL debe incluir un hostname (ej: host.docker.internal)",
                    "examples": cls._get_examples()
                }
            )

        # Check for spaces in netloc (hostname:port)
        if ' ' in parsed.netloc:
            raise URLValidationError(
                "No se permiten espacios en el hostname o puerto",
                url=url,
                details={
                    "found": parsed.netloc,
                    "examples": cls._get_examples()
                }
            )

        # Check path doesn't contain port-like patterns (common error)
        if parsed.path:
            for pattern, description in cls.PORT_IN_PATH_PATTERNS:
                if re.search(pattern, parsed.path):
                    raise URLValidationError(
                        f"URL malformada: {description}",
                        url=url,
                        details={
                            "hostname": parsed.netloc,
                            "path": parsed.path,
                            "pattern_matched": pattern,
                            "issue": description,
                            "hint": "El formato debe ser http://hostname:puerto no http://hostname/algo:puerto",
                            "examples": cls._get_examples()
                        }
                    )

        # Normalize: remove trailing slash, query params, fragments
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

        return normalized

    @classmethod
    def _get_examples(cls) -> list[str]:
        """Return example valid URLs."""
        return [
            "http://host.docker.internal:8555",
            "http://localhost:8555",
            "http://127.0.0.1:8555",
            "http://fabricacion_api:8000",
            "https://api.fabricacion.com",
        ]

    @classmethod
    def is_docker_internal(cls, url: str) -> bool:
        """Check if URL uses Docker-internal hostname."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            return hostname.lower() in cls.DOCKER_HOSTNAMES
        except Exception:
            return False
