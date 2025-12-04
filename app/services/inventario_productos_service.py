from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from ..repositories import (
    InventarioProductosRepository,
    InventarioPiezasRepository,
)
from ..models import InventarioProducto, Proveedor
from ..domain import normalize_estado, normalize_producto_codigo
from .fabricacion_service import FabricacionService
from .proveedores_service import ProveedoresService


class InventarioProductosService:
    def __init__(
        self,
        session: Session,
        repository: InventarioProductosRepository | None = None,
        piezas_repository: InventarioPiezasRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or InventarioProductosRepository(session)
        self.piezas_repository = piezas_repository or InventarioPiezasRepository(session)
        self.fabricacion_service = FabricacionService()
        self.proveedores_service = ProveedoresService(
            session, piezas_repository=self.piezas_repository
        )
        self.stock_minimo = 500
        self.stock_objetivo = 1000
        self.lote_produccion = 500
        self.piezas_stock_minimo = 500
        self.piezas_stock_objetivo = 1000

    def list(self) -> list[InventarioProducto]:
        return self.repository.get_all()

    def list_by_producto(self, producto_id: str) -> list[InventarioProducto]:
        codigo = normalize_producto_codigo(producto_id)
        return (
            self.session.query(InventarioProducto)
            .filter_by(id_producto=codigo)
            .order_by(InventarioProducto.estado)
            .all()
        )

    def retrieve(self, producto_id: str, estado: str) -> InventarioProducto | None:
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado)
        return self.repository.get_by_id((codigo, estado_normalizado))

    def create(self, payload: dict[str, Any]) -> InventarioProducto:
        payload = self._normalize_payload(payload)
        return self.repository.create(**payload)

    def delete(self, producto_id: str, estado: str) -> bool:
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado)
        return self.repository.delete((codigo, estado_normalizado))

    def update(
        self, producto_id: str, estado: str, payload: dict[str, Any]
    ) -> InventarioProducto | None:
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado)
        payload = {k: v for k, v in payload.items() if k == "cantidad"}
        return self.repository.update((codigo, estado_normalizado), **payload)

    def incrementar(
        self, producto_id: str, cantidad: int, estado: str | None = None
    ) -> InventarioProducto:
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado or "Disponible")
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        registro = self.repository.get_by_id((codigo, estado_normalizado))
        if registro:
            registro.cantidad += cantidad
            self.session.commit()
            return registro
        return self.repository.create(
            id_producto=codigo, estado=estado_normalizado, cantidad=cantidad
        )

    def transferir(
        self, producto_id: str, estado_origen: str, estado_destino: str, cantidad: int
    ) -> list[InventarioProducto]:
        codigo = normalize_producto_codigo(producto_id)
        origen = normalize_estado(estado_origen)
        destino = normalize_estado(estado_destino)

        if origen == destino:
            raise ValueError("El estado de origen y destino deben ser diferentes")

        origen_registro = self.repository.get_by_id((codigo, origen))
        destino_registro = self.repository.get_by_id((codigo, destino))
        if not origen_registro or not destino_registro:
            raise ValueError("No se encontraron registros para el producto y estado")

        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        if origen_registro.cantidad < cantidad:
            raise ValueError("Cantidad insuficiente en el estado de origen")

        origen_registro.cantidad -= cantidad
        destino_registro.cantidad += cantidad
        self.session.commit()

        return self.list_by_producto(codigo)

    def reservar_para_venta(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser mayor a cero")

        disponible = self.repository.get_by_id((codigo, "Disponible"))
        if not disponible:
            registros = self.list_by_producto(codigo)
            disponible_actual = next(
                (item for item in registros if item.estado == "Disponible"), None
            )
            disponibilidad = disponible_actual.cantidad if disponible_actual else 0
            return {
                "id_producto": codigo,
                "cantidad_solicitada": cantidad,
                "cantidad_confirmada": 0,
                "cantidad_pendiente": cantidad,
                "cantidad_disponible": disponibilidad,
                "tiempo_estimado": self._tiempo_estimado_reposicion(),
                "reservado": False,
            }

        estado_ingreso = "Reservado"
        if disponible.cantidad >= cantidad:
            registros = self.transferir(codigo, "Disponible", "Reservado", cantidad)
            reservado = True
            confirmada = cantidad
            pendiente = 0
            tiempo_estimado = 0
            fabricado = False
        else:
            registros = self.list_by_producto(codigo)
            disponible_actual = next(
                (item for item in registros if item.estado == "Disponible"),
                None,
            )
            desde_stock = disponible_actual.cantidad if disponible_actual else 0
            if desde_stock > 0:
                self.transferir(
                    codigo, "Disponible", "Reservado", min(desde_stock, cantidad)
                )
            faltante = max(cantidad - desde_stock, 0)
            resultado_fabricacion = self._producir_para_venta(codigo, faltante)
            registros = self.list_by_producto(codigo)
            reservado = True
            confirmada = cantidad
            pendiente = 0
            tiempo_estimado = resultado_fabricacion["tiempo_total"]
            estado_ingreso = "A Despacho"
            fabricado = True

        disponible_actual = next(
            (item for item in registros if item.estado == "Disponible"),
            None,
        )
        respuesta = {
            "id_producto": codigo,
            "cantidad_solicitada": cantidad,
            "cantidad_confirmada": confirmada,
            "cantidad_pendiente": pendiente,
            "cantidad_disponible": disponible_actual.cantidad
            if disponible_actual
            else 0,
            "tiempo_estimado": tiempo_estimado,
            "reservado": reservado,
            "estado_ingreso": estado_ingreso,
            "fabricado": fabricado,
        }
        auto_info = self._evaluar_stock_minimo(codigo)
        respuesta["tiempo_estimado"] = max(
            respuesta["tiempo_estimado"], auto_info["tiempo_estimado"]
        )
        return respuesta

    def despachar_para_venta(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser mayor a cero")

        reservado_registro = self.repository.get_by_id((codigo, "Reservado"))
        estado_ingreso = "A Despacho"
        tiempo_estimado = 0
        confirmada = 0
        faltante = cantidad
        if reservado_registro and reservado_registro.cantidad > 0:
            usar = min(reservado_registro.cantidad, cantidad)
            if usar > 0:
                self.transferir(codigo, "Reservado", "A Despacho", usar)
                confirmada += usar
                faltante -= usar

        if faltante > 0:
            resultado_fabricacion = self._producir_para_venta(codigo, faltante)
            confirmada += faltante
            tiempo_estimado = resultado_fabricacion["tiempo_total"]

        registros = self.list_by_producto(codigo)
        disponible_actual = next(
            (item for item in registros if item.estado == "Disponible"),
            None,
        )

        respuesta = {
            "id_producto": codigo,
            "cantidad_solicitada": cantidad,
            "cantidad_confirmada": confirmada,
            "cantidad_pendiente": max(cantidad - confirmada, 0),
            "cantidad_disponible": disponible_actual.cantidad
            if disponible_actual
            else 0,
            "tiempo_estimado": tiempo_estimado,
            "despachado": True,
            "estado_ingreso": estado_ingreso,
        }
        auto_info = self._evaluar_stock_minimo(codigo)
        respuesta["tiempo_estimado"] = max(
            respuesta["tiempo_estimado"], auto_info["tiempo_estimado"]
        )
        return respuesta

    def fabricar_productos(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        resultado = self._producir_lote(codigo, cantidad)
        disponible = self.repository.get_by_id((codigo, "Disponible"))
        disponible_actual = disponible.cantidad if disponible else 0
        return {
            "id_producto": codigo,
            "cantidad_producida": cantidad,
            "tiempo_reabastecimiento": resultado["tiempo_reabastecimiento"],
            "tiempo_produccion": resultado["tiempo_produccion"],
            "tiempo_total": resultado["tiempo_total"],
            "inventario_disponible": disponible_actual,
        }

    def _tiempo_estimado_reposicion(self) -> int:
        proveedor = (
            self.session.query(Proveedor).order_by(Proveedor.tiempo).first()
        )
        return proveedor.tiempo if proveedor else 0

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["id_producto"] = normalize_producto_codigo(data.get("id_producto", ""))
        data["estado"] = normalize_estado(data.get("estado", ""))
        if "cantidad" not in data:
            data["cantidad"] = 0
        return data

    def _evaluar_stock_minimo(self, codigo: str) -> dict[str, int]:
        disponible = self.repository.get_by_id((codigo, "Disponible"))
        if not disponible or disponible.cantidad >= self.stock_minimo:
            return {"tiempo_estimado": 0, "produccion_solicitada": 0}
        return self._producir_hasta_objetivo(codigo, disponible)

    def _producir_hasta_objetivo(
        self, codigo: str, disponible: InventarioProducto | None
    ) -> dict[str, int]:
        tiempo_total = 0
        produccion_total = 0
        while True:
            disponible_actual = self.repository.get_by_id((codigo, "Disponible"))
            actual = disponible_actual.cantidad if disponible_actual else 0
            if actual >= self.stock_objetivo:
                break
            resultado = self._producir_lote(codigo, self.lote_produccion)
            tiempo_total += resultado["tiempo_total"]
            produccion_total += self.lote_produccion
        return {
            "tiempo_estimado": tiempo_total,
            "produccion_solicitada": produccion_total,
        }

    def _producir_para_venta(self, codigo: str, cantidad: int) -> dict[str, int]:
        if cantidad <= 0:
            return {
                "tiempo_total": 0,
                "tiempo_reabastecimiento": 0,
                "tiempo_produccion": 0,
            }
        return self._producir_lote(codigo, cantidad, estado_destino="A Despacho")

    def _producir_lote(
        self, codigo: str, cantidad: int, estado_destino: str = "Disponible"
    ) -> dict[str, int]:
        plan = self.fabricacion_service.solicitar_plan(codigo, cantidad)
        tiempo_reabastecimiento = self._asegurar_piezas(plan.materiales)

        piezas_suficientes = True
        for material in plan.materiales:
            pieza = self.piezas_repository.get_by_id(material["id_pieza"])
            if not pieza or pieza.cantidad < material["cantidad"]:
                piezas_suficientes = False
                break

        if not piezas_suficientes:
            raise ValueError("No hay suficientes piezas disponibles para fabricar")

        confirmacion = self.fabricacion_service.confirmar_fabricacion_externa(
            codigo, cantidad
        )

        if confirmacion and confirmacion.get("status") == "ok":
            for material in plan.materiales:
                pieza = self.piezas_repository.get_by_id(material["id_pieza"])
                if pieza:
                    pieza.cantidad -= material["cantidad"]
            self.session.commit()
            return {
                "tiempo_total": tiempo_reabastecimiento + plan.tiempo_produccion,
                "tiempo_produccion": plan.tiempo_produccion,
                "tiempo_reabastecimiento": tiempo_reabastecimiento,
                "fabricacion_externa": True,
                "estado_fabricacion": "enviado_a_fabrica_externa",
                "mensaje": f"Piezas enviadas a fábrica. Esperando productos de {codigo} x{cantidad}",
            }

        # Fallback local cuando no hay fábrica externa disponible
        for material in plan.materiales:
            pieza = self.piezas_repository.get_by_id(material["id_pieza"])
            if pieza:
                pieza.cantidad -= material["cantidad"]

        registro_destino = self.repository.get_by_id((codigo, estado_destino))
        if not registro_destino:
            registro_destino = InventarioProducto(
                id_producto=codigo, estado=estado_destino, cantidad=0
            )
            self.session.add(registro_destino)
        registro_destino.cantidad += cantidad
        self.session.commit()

        return {
            "tiempo_total": tiempo_reabastecimiento + plan.tiempo_produccion,
            "tiempo_produccion": plan.tiempo_produccion,
            "tiempo_reabastecimiento": tiempo_reabastecimiento,
            "fabricacion_externa": False,
            "estado_fabricacion": "local",
            "mensaje": f"Producción local completada para {codigo} x{cantidad}",
        }

    def _asegurar_piezas(self, materiales: list[dict]) -> int:
        tiempo_max = 0
        for material in materiales:
            pieza = self.piezas_repository.get_by_id(material["id_pieza"])
            if not pieza:
                raise ValueError(f"No existe la pieza {material['id_pieza']}")
            saldo_post_consumo = pieza.cantidad - material["cantidad"]
            if saldo_post_consumo < self.piezas_stock_minimo:
                faltante = max(
                    material["cantidad"] + self.piezas_stock_objetivo - pieza.cantidad,
                    0,
                )
                if faltante > 0:
                    resultado = self.proveedores_service.solicitar_piezas(
                        pieza.id_pieza, faltante
                    )
                    tiempo_max = max(tiempo_max, resultado["tiempo_entrega"])
        self.session.commit()
        return tiempo_max
