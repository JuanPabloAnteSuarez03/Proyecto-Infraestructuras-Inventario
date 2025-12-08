"""
Helper para coordinar fabricación y reposición de productos.

Este módulo maneja la lógica compleja de coordinación entre inventario,
fabricación y proveedores para garantizar niveles de stock adecuados.
"""

from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from app.repositories import InventarioPiezasRepository
from app.models import Proveedor
from app.domain import normalize_producto_codigo
from app.services.fabricacion.fabricacion_service import FabricacionService
from app.services.proveedores.proveedores_service import ProveedoresService
from app.services.proveedores.solicitudes_service import SolicitudesPiezaService


class ProductosManufacturingHelper:
    """
    Helper para manejar la lógica de fabricación y reposición de productos.

    Coordina con:
    - Servicio de fabricación para obtener planes y tiempos
    - Servicio de proveedores para solicitar piezas faltantes
    - Repositorio de piezas para validar y consumir materiales
    """

    def __init__(
        self,
        session: Session,
        piezas_repository: InventarioPiezasRepository,
        fabricacion_service: FabricacionService | None = None,
        proveedores_service: ProveedoresService | None = None,
    ):
        """
        Inicializa el helper de manufactura.

        Args:
            session: Sesión de base de datos
            piezas_repository: Repositorio de piezas
            fabricacion_service: Servicio de fabricación (opcional)
            proveedores_service: Servicio de proveedores (opcional)
        """
        self.session = session
        self.piezas_repository = piezas_repository
        self.fabricacion_service = fabricacion_service or FabricacionService()
        self.proveedores_service = proveedores_service or ProveedoresService(
            session, piezas_repository=piezas_repository
        )
        self.solicitudes_service = SolicitudesPiezaService(session)

    def producir_lote(
        self,
        codigo: str,
        cantidad: int,
        incrementar_callback: callable,
    ) -> dict[str, Any]:
        """
        Produce un lote de productos, gestionando piezas y tiempos.

        Args:
            codigo: Código del producto a fabricar
            cantidad: Cantidad a producir
            incrementar_callback: Función para incrementar inventario

        Returns:
            Dict con información de tiempos de producción

        Raises:
            ValueError: Si no hay piezas suficientes o no existe una pieza
        """
        plan = self.fabricacion_service.solicitar_plan(codigo, cantidad)
        tiempo_reabastecimiento = self._solicitar_piezas_faltantes(plan.materiales)
        tiempo_produccion = plan.tiempo_produccion

        # Consumir materiales
        for material in plan.materiales:
            pieza = self.piezas_repository.get_by_id(material["id_pieza"])
            if pieza is None:
                raise ValueError(
                    f"Pieza {material['id_pieza']} no existe en inventario"
                )
            if pieza.cantidad < material["cantidad"]:
                raise ValueError(
                    f"No hay suficiente cantidad de la pieza {material['id_pieza']} "
                    f"para fabricar"
                )
            pieza.cantidad -= material["cantidad"]

        # Incrementar productos usando callback
        incrementar_callback(codigo, cantidad)

        return {
            "tiempo_reabastecimiento": tiempo_reabastecimiento,
            "tiempo_produccion": tiempo_produccion,
            "tiempo_total": tiempo_reabastecimiento + tiempo_produccion,
        }

    def evaluar_stock_minimo(
        self,
        codigo: str,
        cantidad_disponible: int,
        stock_minimo: int,
        stock_objetivo: int,
        lote_produccion: int,
    ) -> dict[str, int | str]:
        """
        Evalúa si el stock está por debajo del mínimo y calcula reposición.

        Args:
            codigo: Código del producto
            cantidad_disponible: Cantidad actualmente disponible
            stock_minimo: Umbral mínimo de stock
            stock_objetivo: Stock objetivo a alcanzar
            lote_produccion: Tamaño de lote de producción

        Returns:
            Dict con tiempo estimado, acción y cantidad a reponer (si aplica)
        """
        if cantidad_disponible >= stock_minimo:
            return {"tiempo_estimado": 0, "accion": "ok"}

        cantidad_a_producir = max(stock_objetivo - cantidad_disponible, 0)
        if cantidad_a_producir <= 0:
            return {"tiempo_estimado": 0, "accion": "ok"}

        cantidad_reponer = max(cantidad_a_producir, lote_produccion)
        plan = self.fabricacion_service.solicitar_plan(
            codigo, cantidad_reponer
        )

        tiempo_reabastecimiento = self._solicitar_piezas_faltantes(plan.materiales)
        tiempo_produccion = plan.tiempo_produccion

        return {
            "tiempo_estimado": tiempo_reabastecimiento + tiempo_produccion,
            "accion": "fabricar",
            "cantidad_reponer": cantidad_reponer,
        }

    def _solicitar_piezas_faltantes(self, materiales: list[dict]) -> int:
        """
        Solicita a proveedores las piezas faltantes para producción.

        Args:
            materiales: Lista de materiales requeridos

        Returns:
            Tiempo máximo de reabastecimiento en minutos
        """
        tiempo_reabastecimiento = 0
        for material in materiales:
            pieza = self.piezas_repository.get_by_id(material["id_pieza"])
            disponible = pieza.cantidad if pieza else 0

            if disponible < material["cantidad"]:
                faltante = material["cantidad"] - disponible
                eta = pieza.proveedor.tiempo if pieza and pieza.proveedor else 0
                solicitud = self.solicitudes_service.create(
                    {
                        "id_pieza": material["id_pieza"],
                        "cantidad": faltante,
                        "estado": "en_proceso",
                        "tiempo_estimado": eta,
                    }
                )
                resultado = self.proveedores_service.solicitar_piezas(
                    material["id_pieza"], faltante
                )
                tiempo_entrega = resultado.get("tiempo_entrega", eta)
                tiempo_reabastecimiento = max(
                    tiempo_reabastecimiento, tiempo_entrega
                )
                self.solicitudes_service.update(
                    solicitud.id,
                    {"estado": "completada", "tiempo_estimado": tiempo_entrega},
                )

        return tiempo_reabastecimiento

    @staticmethod
    def tiempo_estimado_reposicion(session: Session) -> int:
        """
        Obtiene el tiempo estimado de reposición del proveedor más rápido.

        Args:
            session: Sesión de base de datos

        Returns:
            Tiempo de entrega en minutos del proveedor más rápido
        """
        proveedor: Proveedor | None = (
            session.query(Proveedor).order_by(Proveedor.tiempo.asc()).first()
        )
        return proveedor.tiempo if proveedor else 0
