from __future__ import annotations
import os
import logging
from dataclasses import dataclass
import httpx
from app.domain.fabricacion import obtener_plan
from app.core.redis_client import get_redis
from app.utils.url_validator import FabricationURLValidator, URLValidationError

logger = logging.getLogger(__name__)


@dataclass
class PlanFabricacion:
    materiales: list[dict]
    tiempo_produccion: int
    fuente_datos: str = "interno"  # "externo" cuando viene de la fábrica


class FabricacionService:
    """Cliente/estrategia para planes y confirmaciones de fábrica externa con fallback local."""

    _override_base_url: str | None = None
    _redis_key = "fabricacion:base_url"
    _default_fallback = "http://host.docker.internal:8555"
    _local_fallback = "http://localhost:8555"

    def __init__(self) -> None:
        self.plano_mapping = {"S1": 1, "S2": 2}
        # La fábrica externa espera "S1" y "S2", no "1" y "2"
        self.codigo_externo_mapping = {"S1": "S1", "S2": "S2"}

    @classmethod
    def set_base_url(cls, base_url: str | None) -> None:
        """
        Persiste la URL base en Redis para que API y worker compartan la misma configuración.
        También mantiene un override en memoria para el proceso actual.

        Raises:
            URLValidationError: Si la URL es malformada o inválida
        """
        # Validate URL before storing (raises URLValidationError if invalid)
        if base_url is not None and base_url.strip():
            url = FabricationURLValidator.validate(base_url, allow_empty=False)
        else:
            url = None

        cls._override_base_url = url or None
        try:
            client = get_redis()
            if url:
                client.set(cls._redis_key, url)
            else:
                client.delete(cls._redis_key)
        except Exception:
            # No bloquear por errores de Redis; se mantendrá el override local
            pass

    @classmethod
    def get_base_url(cls) -> str:
        """
        Obtiene la base URL priorizando:
        1) valor en Redis (persistente y compartido),
        2) override en memoria del proceso actual,
        3) variable de entorno FABRICA_BASE_URL.

        Valida URLs recuperadas de Redis para detectar datos corruptos.
        """
        # Redis persistente
        try:
            client = get_redis()
            stored = client.get(cls._redis_key)
            if stored:
                url = stored.decode().rstrip("/")
                # Defensive: validate URL from Redis
                try:
                    validated_url = FabricationURLValidator.validate(url, allow_empty=False)
                    return validated_url
                except URLValidationError as e:
                    logger.warning(
                        f"URL malformada encontrada en Redis, limpiando: {url}. Error: {e.message}"
                    )
                    # Auto-cleanup: delete malformed URL
                    client.delete(cls._redis_key)
                    # Fall through to next priority
        except Exception as e:
            logger.debug(f"Error de Redis al obtener base URL: {e}")
            pass

        # Override en memoria (proceso actual)
        if cls._override_base_url:
            return cls._override_base_url.rstrip("/")

        # Fallback a entorno
        env_url = os.getenv("FABRICA_BASE_URL", "").rstrip("/")
        return env_url

    @classmethod
    def candidate_base_urls(cls) -> list[str]:
        """
        Devuelve la lista de URLs candidatas (persistida y fallback local) sin duplicados,
        para probar conexión con la fábrica.
        """
        bases: list[str] = []
        primary = cls.get_base_url()
        env_fallback = os.getenv("FABRICA_BASE_URL_FALLBACK", "").rstrip("/")
        for url in (primary, env_fallback, cls._default_fallback, cls._local_fallback, "http://127.0.0.1:8555"):
            if url and url not in bases:
                bases.append(url)
        return bases

    def _base_url(self) -> str:
        # Mantener compatibilidad: regresa la primera base disponible
        bases = self.candidate_base_urls()
        return bases[0] if bases else ""

    def _persist_if_different(self, base_url: str) -> None:
        """Guarda en Redis la URL que funcionó para que API y worker usen la misma."""
        try:
            current = self.get_base_url()
            if base_url and base_url != current:
                self.set_base_url(base_url)
        except Exception:
            pass

    def _tiempo_desde_fabrica(self, codigo: str) -> int | None:
        plano_id = self.plano_mapping.get(codigo.upper())
        if not plano_id:
            return None
        for base in self.candidate_base_urls():
            url = f"{base}/fabricacion/planos/{plano_id}"
            try:
                resp = httpx.get(url, timeout=5)
                resp.raise_for_status()
                data = resp.json()
                self._persist_if_different(base)
                return int(data.get("tiempo_fabricacion", 0)) or None
            except Exception:
                continue
        return None

    def _calculo_piezas_externo(self, codigo: str, cantidad: int) -> list[dict] | None:
        """Intenta usar el endpoint externo /fabricacion/calculo_piezas."""
        codigo_externo = self.codigo_externo_mapping.get(codigo.upper(), codigo)
        for base in self.candidate_base_urls():
            url = f"{base}/fabricacion/calculo_piezas"
            try:
                resp = httpx.post(url, json={"codigo": codigo_externo, "cantidad": cantidad}, timeout=5)
                resp.raise_for_status()
                data = resp.json()
                materiales = []
                for item in data.get("piezas", []):
                    materiales.append({"id_pieza": item["codigo_pieza"], "cantidad": item["total_piezas"]})
                if materiales:
                    self._persist_if_different(base)
                    return materiales
            except Exception:
                continue
        return None

    def obtener_plan_base(self, codigo: str) -> dict:
        return obtener_plan(codigo)

    def solicitar_plan(self, codigo: str, cantidad: int) -> PlanFabricacion:
        tiempo_base = self._tiempo_desde_fabrica(codigo)
        materiales_externos = self._calculo_piezas_externo(codigo, cantidad)

        if materiales_externos:
            materiales = materiales_externos
            tiempo_produccion = (tiempo_base or 0) * max(cantidad // 100, 1) if tiempo_base else 0
            if tiempo_produccion == 0:
                tiempo_produccion = obtener_plan(codigo)["tiempo_produccion"] * max(cantidad // 100, 1)
            return PlanFabricacion(materiales=materiales, tiempo_produccion=tiempo_produccion, fuente_datos="externo")

        base_plan = obtener_plan(codigo)
        tiempo = tiempo_base or base_plan["tiempo_produccion"]
        materiales = [
            {"id_pieza": item["id_pieza"], "cantidad": item["cantidad"] * cantidad}
            for item in base_plan["piezas"]
        ]
        tiempo_produccion = tiempo * max(cantidad // 100, 1)
        return PlanFabricacion(materiales=materiales, tiempo_produccion=tiempo_produccion, fuente_datos="interno")

    def confirmar_fabricacion_externa(self, codigo: str, cantidad: int) -> dict | None:
        """Envía orden de fabricación al servicio externo y retorna confirmación."""
        codigo_externo = self.codigo_externo_mapping.get(codigo.upper(), codigo)
        for base in self.candidate_base_urls():
            url = f"{base}/fabricacion/confirmar_fabricacion"
            try:
                resp = httpx.post(
                    url,
                    json={"codigo": codigo_externo, "cantidad": cantidad},
                    timeout=10,
                )
                resp.raise_for_status()
                self._persist_if_different(base)
                return resp.json()
            except Exception as e:
                last_error = e
                continue
        if "last_error" in locals():
            print(f"[ERROR] Fallo al confirmar con fábrica externa: {last_error}")
        return None
