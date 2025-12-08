from __future__ import annotations
import logging
from typing import Any
from sqlalchemy.orm import Session
from app.repositories import (
    InventarioProductosRepository,
    InventarioPiezasRepository,
)
from app.models import InventarioProducto
from app.domain import normalize_estado, normalize_producto_codigo
from app.services.inventario.productos_manufacturing_helper import (
    ProductosManufacturingHelper,
)
from app.services.fabricacion.fabricacion_orchestrator import FabricacionOrchestrator


class InventarioProductosService:
    """
    Servicio para gestionar el inventario de productos terminados.

    Maneja productos en tres estados: Disponible, Reservado y A Despacho.
    Coordina con servicios de fabricación y proveedores para mantener
    niveles de stock óptimos mediante reposición automática.

    Responsabilidades:
    - CRUD de productos en inventario
    - Transferencias entre estados
    - Reservas para ventas con reposición automática
    - Despachos de productos
    - Coordinación con fabricación cuando stock es bajo
    """

    def __init__(
        self,
        session: Session,
        repository: InventarioProductosRepository | None = None,
        piezas_repository: InventarioPiezasRepository | None = None,
    ) -> None:
        """
        Inicializa el servicio de inventario de productos.

        Args:
            session: Sesión de base de datos SQLAlchemy
            repository: Repositorio de productos (opcional, se crea si no se provee)
            piezas_repository: Repositorio de piezas (opcional, se crea si no se provee)
        """
        self.session = session
        self.repository = repository or InventarioProductosRepository(session)
        self.piezas_repository = piezas_repository or InventarioPiezasRepository(
            session
        )

        # Helper para lógica de fabricación
        self.manufacturing_helper = ProductosManufacturingHelper(
            session=session,
            piezas_repository=self.piezas_repository,
        )

        # Configuración de políticas de stock
        self.stock_minimo = 500
        self.stock_objetivo = 1000
        self.lote_produccion = 500
        self.log = logging.getLogger(self.__class__.__name__)

    # === CRUD Operations ===

    def list(self) -> list[InventarioProducto]:
        """
        Obtiene todos los productos en inventario (todos los estados).

        Returns:
            Lista de todos los registros de inventario de productos
        """
        return self.repository.get_all()

    def list_by_producto(self, producto_id: str) -> list[InventarioProducto]:
        """
        Obtiene todos los estados de un producto específico.

        Args:
            producto_id: Código del producto (S1, S2, etc.)

        Returns:
            Lista de registros del producto en diferentes estados,
            ordenados por estado
        """
        codigo = normalize_producto_codigo(producto_id)
        return (
            self.session.query(InventarioProducto)
            .filter_by(id_producto=codigo)
            .order_by(InventarioProducto.estado)
            .all()
        )

    def retrieve(self, producto_id: str, estado: str) -> InventarioProducto | None:
        """
        Obtiene un producto específico en un estado específico.

        Args:
            producto_id: Código del producto
            estado: Estado del producto (Disponible, Reservado, A Despacho)

        Returns:
            Registro del producto o None si no existe
        """
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado)
        return self.repository.get_by_id((codigo, estado_normalizado))

    def create(self, payload: dict[str, Any]) -> InventarioProducto:
        """
        Crea un nuevo registro de producto en inventario.

        Args:
            payload: Datos del producto (id_producto, estado, cantidad)

        Returns:
            Producto creado
        """
        payload = self._normalize_payload(payload)
        return self.repository.create(**payload)

    def update(
        self, producto_id: str, estado: str, payload: dict[str, Any]
    ) -> InventarioProducto | None:
        """
        Actualiza la cantidad de un producto en un estado específico.

        Args:
            producto_id: Código del producto
            estado: Estado del producto
            payload: Datos a actualizar (solo cantidad permitida)

        Returns:
            Producto actualizado o None si no existe
        """
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado)
        # Solo permitir actualización de cantidad
        payload = {k: v for k, v in payload.items() if k == "cantidad"}
        return self.repository.update((codigo, estado_normalizado), **payload)

    def delete(self, producto_id: str, estado: str) -> bool:
        """
        Elimina un registro de producto.

        Args:
            producto_id: Código del producto
            estado: Estado del producto

        Returns:
            True si fue eliminado, False si no existía
        """
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado)
        return self.repository.delete((codigo, estado_normalizado))

    def reset_all(self) -> int:
        """
        Resetea todas las cantidades de productos a cero.

        ADVERTENCIA: Esta operación es destructiva y afecta todos los productos
        en todos los estados.

        Returns:
            Número de registros actualizados
        """
        updated = self.session.query(InventarioProducto).update({"cantidad": 0})
        self.session.commit()
        return updated

    # === Inventory Operations ===

    def incrementar(
        self, producto_id: str, cantidad: int, estado: str | None = None
    ) -> InventarioProducto:
        """
        Incrementa la cantidad de un producto en un estado específico.

        Si el registro no existe, lo crea. Esta operación es thread-safe
        mediante locking de filas.

        Args:
            producto_id: Código del producto
            cantidad: Cantidad a incrementar (debe ser > 0)
            estado: Estado donde incrementar (default: Disponible)

        Returns:
            Registro actualizado o creado

        Raises:
            ValueError: Si cantidad <= 0
        """
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado or "Disponible")

        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        # Lock optimista para evitar condiciones de carrera
        registro = (
            self.session.query(InventarioProducto)
            .filter_by(id_producto=codigo, estado=estado_normalizado)
            .with_for_update()
            .first()
        )

        if registro:
            registro.cantidad += cantidad
            self.session.commit()
            self.session.refresh(registro)
            return registro

        # Crear nuevo registro si no existe
        nuevo = InventarioProducto(
            id_producto=codigo, estado=estado_normalizado, cantidad=cantidad
        )
        self.session.add(nuevo)
        self.session.commit()
        self.session.refresh(nuevo)
        return nuevo

    def transferir(
        self, producto_id: str, estado_origen: str, estado_destino: str, cantidad: int
    ) -> list[InventarioProducto]:
        """
        Transfiere productos entre estados.

        Args:
            producto_id: Código del producto
            estado_origen: Estado de origen
            estado_destino: Estado de destino
            cantidad: Cantidad a transferir

        Returns:
            Lista de todos los estados del producto después de la transferencia

        Raises:
            ValueError: Si los estados son iguales, no existen, cantidad inválida
                       o no hay suficiente stock en origen
        """
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

        # Realizar transferencia
        origen_registro.cantidad -= cantidad
        destino_registro.cantidad += cantidad
        self.session.commit()

        return self.list_by_producto(codigo)

    # === Business Operations ===

    def reservar_para_venta(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Reserva productos para una venta.

        Intenta reservar desde stock disponible. Si no hay suficiente,
        activa producción automática.

        Args:
            producto_id: Código del producto
            cantidad: Cantidad a reservar

        Returns:
            Dict con información de la reserva:
            - id_producto: Código del producto
            - cantidad_solicitada: Cantidad solicitada
            - cantidad_confirmada: Cantidad efectivamente reservada
            - cantidad_pendiente: Cantidad pendiente de producción
            - cantidad_disponible: Stock disponible después de la operación
            - tiempo_estimado: Tiempo estimado en minutos
            - estado_ingreso: Estado donde se ingresará
            - reservado: Si la reserva fue exitosa
            - fabricado: Si se activó fabricación

        Raises:
            ValueError: Si cantidad <= 0
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser mayor a cero")

        disponible = self.repository.get_by_id((codigo, "Disponible"))
        if not disponible:
            # No hay registro de disponible
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
                "tiempo_estimado": ProductosManufacturingHelper.tiempo_estimado_reposicion(
                    self.session
                ),
                "reservado": False,
                "estado_ingreso": "Reservado",
                "fabricado": False,
            }

        estado_ingreso = "Reservado"
        fabricado = False

        # Caso 1: Hay suficiente stock disponible
        if disponible.cantidad >= cantidad:
            registros = self.transferir(codigo, "Disponible", "Reservado", cantidad)
            confirmada = cantidad
            pendiente = 0
            tiempo_estimado = 0

        # Caso 2: Stock insuficiente, activar fabricación
        else:
            registros = self.list_by_producto(codigo)
            disponible_actual = next(
                (item for item in registros if item.estado == "Disponible"),
                None,
            )
            desde_stock = disponible_actual.cantidad if disponible_actual else 0

            # Usar lo que hay disponible
            if desde_stock > 0:
                self.transferir(
                    codigo, "Disponible", "Reservado", min(desde_stock, cantidad)
                )

            # Fabricar lo faltante
            faltante = max(cantidad - desde_stock, 0)
            resultado_fabricacion = self._producir_para_venta(codigo, faltante)

            registros = self.list_by_producto(codigo)
            confirmada = cantidad
            pendiente = 0
            tiempo_estimado = resultado_fabricacion["tiempo_total"]
            estado_ingreso = "A Despacho"
            fabricado = True

        # Calcular disponibilidad final
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
            "reservado": True,
            "estado_ingreso": estado_ingreso,
            "fabricado": fabricado,
        }

        if respuesta["cantidad_pendiente"] == 0:
            respuesta["tiempo_estimado"] = 0

        return respuesta

    def despachar_para_venta(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Despacha productos para entrega.

        Intenta despachar desde stock reservado. Si no hay suficiente,
        activa producción automática.

        Args:
            producto_id: Código del producto
            cantidad: Cantidad a despachar

        Returns:
            Dict con información del despacho (similar a reservar_para_venta)

        Raises:
            ValueError: Si cantidad <= 0
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser mayor a cero")

        reservado_registro = self.repository.get_by_id((codigo, "Reservado"))
        estado_ingreso = "A Despacho"
        tiempo_estimado = 0
        confirmada = 0
        faltante = cantidad

        # Usar stock reservado si existe
        if reservado_registro and reservado_registro.cantidad > 0:
            usar = min(reservado_registro.cantidad, cantidad)
            if usar > 0:
                self.transferir(codigo, "Reservado", "A Despacho", usar)
                confirmada += usar
                faltante -= usar

        # Fabricar lo faltante si es necesario
        if faltante > 0:
            resultado_fabricacion = self._producir_para_venta(codigo, faltante)
            confirmada += faltante
            tiempo_estimado = resultado_fabricacion["tiempo_total"]

        # Obtener disponibilidad actual
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

        if respuesta["cantidad_pendiente"] == 0:
            respuesta["tiempo_estimado"] = 0

        return respuesta

    def fabricar_productos(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Fabrica productos y los agrega al inventario disponible.

        Args:
            producto_id: Código del producto a fabricar
            cantidad: Cantidad a fabricar

        Returns:
            Dict con información de producción

        Raises:
            ValueError: Si cantidad <= 0 o hay problemas con piezas
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        resultado = self.manufacturing_helper.producir_lote(
            codigo, cantidad, self.incrementar
        )

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

    # === Private Helper Methods ===

    def _producir_para_venta(self, codigo: str, cantidad: int) -> dict[str, Any]:
        """Produce un lote para cumplir con una venta."""
        return self.manufacturing_helper.producir_lote(
            codigo, cantidad, self.incrementar
        )

    def _evaluar_stock_minimo(self, producto_id: str) -> dict[str, int]:
        """
        Evalúa si el stock está por debajo del mínimo.

        Returns:
            Dict con tiempo_estimado y accion
        """
        codigo = normalize_producto_codigo(producto_id)
        registros = self.list_by_producto(codigo)
        disponible = next(
            (item for item in registros if item.estado == "Disponible"), None
        )
        cantidad_disponible = disponible.cantidad if disponible else 0

        return self.manufacturing_helper.evaluar_stock_minimo(
            codigo=codigo,
            cantidad_disponible=cantidad_disponible,
            stock_minimo=self.stock_minimo,
            stock_objetivo=self.stock_objetivo,
            lote_produccion=self.lote_produccion,
        )

    def _encolar_reposicion(self, codigo: str, cantidad: int) -> None:
        """
        Encola una orden de fabricación para reponer stock mínimo.

        Si la cantidad es <= 0 o si ocurre un error, solo se loguea para diagnóstico
        sin interrumpir la operación original de reserva/despacho.
        """
        if cantidad <= 0:
            return
        try:
            orchestrator = FabricacionOrchestrator(
                session=self.session,
                fabricacion_service=self.manufacturing_helper.fabricacion_service,
            )
            resultado = orchestrator.crear_orden(codigo, cantidad)
            self.log.info(
                "[AUTO_STOCK] Orden de reposición encolada: producto=%s, cantidad=%s, estado=%s",
                codigo,
                cantidad,
                resultado.get("estado"),
            )
        except Exception as exc:
            self.log.warning(
                "[AUTO_STOCK] No se pudo encolar reposición automática para %s x%s: %s",
                codigo,
                cantidad,
                exc,
            )

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normaliza códigos de producto y estado en el payload."""
        payload["id_producto"] = normalize_producto_codigo(
            payload.get("id_producto", "")
        )
        payload["estado"] = normalize_estado(payload.get("estado", ""))
        return payload
