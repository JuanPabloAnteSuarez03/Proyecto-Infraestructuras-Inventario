from __future__ import annotations
import os
from dataclasses import dataclass
import httpx
from ..domain.fabricacion import obtener_plan


@dataclass
class PlanFabricacion:
    materiales: list[dict]
    tiempo_produccion: int


class FabricacionService:
    def __init__(self) -> None:
        self.base_url = os.getenv("FABRICA_BASE_URL", "").rstrip("/")
        self.plano_mapping = {"S1": 1, "S2": 2}

    def _tiempo_desde_fabrica(self, codigo: str) -> int | None:
        if not self.base_url:
            return None
        plano_id = self.plano_mapping.get(codigo.upper())
        if not plano_id:
            return None
        url = f"{self.base_url}/fabricacion/planos/{plano_id}"
        try:
            resp = httpx.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return int(data.get("tiempo_fabricacion", 0)) or None
        except Exception:
            return None

    def _calculo_piezas_externo(self, codigo: str, cantidad: int) -> list[dict] | None:
        """Intenta usar el endpoint externo /fabricacion/calculo_piezas."""
        if not self.base_url:
            return None
        url = f"{self.base_url}/fabricacion/calculo_piezas"
        try:
            resp = httpx.post(url, json={"codigo": codigo, "cantidad": cantidad}, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            materiales = []
            for item in data.get("piezas", []):
                materiales.append(
                    {
                        "id_pieza": item["codigo_pieza"],
                        "cantidad": item["total_piezas"],
                    }
                )
            return materiales if materiales else None
        except Exception:
            return None

    def obtener_plan_base(self, codigo: str) -> dict:
        return obtener_plan(codigo)

    def solicitar_plan(self, codigo: str, cantidad: int) -> PlanFabricacion:
        # Intentar cálculo externo si hay base_url
        tiempo_base = self._tiempo_desde_fabrica(codigo)
        materiales_externos = self._calculo_piezas_externo(codigo, cantidad)

        if materiales_externos:
            materiales = materiales_externos
            tiempo_produccion = (tiempo_base or 0) * max(cantidad // 100, 1) if tiempo_base else 0
            # Si no hay tiempo externo, usa fallback local
            if tiempo_produccion == 0:
                tiempo_produccion = obtener_plan(codigo)["tiempo_produccion"] * max(cantidad // 100, 1)
            return PlanFabricacion(materiales=materiales, tiempo_produccion=tiempo_produccion)

        # Fallback al plan interno
        base_plan = obtener_plan(codigo)
        tiempo = tiempo_base or base_plan["tiempo_produccion"]
        materiales = []
        for item in base_plan["piezas"]:
            materiales.append(
                {
                    "id_pieza": item["id_pieza"],
                    "cantidad": item["cantidad"] * cantidad,
                }
            )
        tiempo_produccion = tiempo * max(cantidad // 100, 1)
        return PlanFabricacion(materiales=materiales, tiempo_produccion=tiempo_produccion)
