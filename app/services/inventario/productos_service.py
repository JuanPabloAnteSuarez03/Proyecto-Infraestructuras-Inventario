from __future__ import annotations
import logging
from typing import Any
from sqlalchemy.orm import Session
from app.repositories import (
    InventarioProductosRepository,
    InventarioPiezasRepository,
    PedidoVentaRepository,
)
from app.models import InventarioProducto, PedidoVenta
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
        pedidos_repository: PedidoVentaRepository | None = None,
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
        self.pedidos_repository = pedidos_repository or PedidoVentaRepository(session)

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
            resultado = registro
        else:
            nuevo = InventarioProducto(
                id_producto=codigo, estado=estado_normalizado, cantidad=cantidad
            )
            self.session.add(nuevo)
            self.session.commit()
            self.session.refresh(nuevo)
            resultado = nuevo

        if estado_normalizado == "Disponible":
            # Intentar satisfacer pedidos completos solo cuando hay stock suficiente
            self._satisfacer_pedidos_completos(codigo)
            actualizado = self.repository.get_by_id((codigo, estado_normalizado))
            if actualizado:
                resultado = actualizado

        return resultado

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
        if not origen_registro:
            raise ValueError("No se encontraron registros para el producto y estado")
        destino_registro = self._ensure_estado_registro(codigo, destino)

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

    def procesar_pedido_online(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Pedido online:
        - Stock completo: Disponible -> A Despacho (entrega inmediata).
        - Stock parcial: mover disponible a Pendiente y fabricar el faltante; todo queda en Pendiente listo para despacho.
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser mayor a cero")

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0
        mover = min(disponible, cantidad)
        faltante = max(cantidad - mover, 0)

        # Garantizar que exista registro Pendiente para recibir entregas posteriores
        self._ensure_estado_registro(codigo, "Pendiente")

        if mover > 0:
            self.transferir(codigo, "Disponible", "Pendiente", mover)

        tiempo_estimado = 0
        orden_id = None
        orden_estado = None
        if faltante > 0:
            # Encolar orden de fabricación para el faltante para que sea visible en dashboard
            orchestrator = FabricacionOrchestrator(
                session=self.session,
                fabricacion_service=self.manufacturing_helper.fabricacion_service,
            )
            resultado = orchestrator.crear_orden(codigo, faltante)
            tiempo_estimado = resultado.get("tiempo_estimado", 0) or 0
            orden_id = resultado.get("id") if isinstance(resultado, dict) else None
            orden_estado = resultado.get("estado") if isinstance(resultado, dict) else None

        pedido = self._crear_pedido_venta(
            tipo="online",
            codigo=codigo,
            cantidad_solicitada=cantidad,
            cantidad_atendida=mover,
            cantidad_faltante=faltante,
            estado_destino="Pendiente",
        )

        pendiente_reg = self.repository.get_by_id((codigo, "Pendiente"))
        return {
            "id_producto": codigo,
            "pedido_id": pedido.id if pedido else None,
            "cantidad_solicitada": cantidad,
            "cantidad_en_pendiente": pendiente_reg.cantidad if pendiente_reg else 0,
            "cantidad_inmediata": mover if faltante == 0 else 0,
            "faltante_fabricado": faltante,
            "tiempo_estimado": tiempo_estimado,
            "estado_destino": "Pendiente",
            "orden_id": orden_id,
            "orden_estado": orden_estado,
            "estado_pedido": pedido.estado if pedido else "abierto",
        }

    def procesar_pedido_local(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Pedido local:
        - Stock completo: Disponible -> Reservado.
        - Stock parcial: mover disponible a Reservado, fabricar faltante y dejar en Reservado.
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser mayor a cero")

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0
        mover = min(disponible, cantidad)
        faltante = max(cantidad - mover, 0)

        if mover > 0:
            self.transferir(codigo, "Disponible", "Reservado", mover)

        tiempo_estimado = 0
        orden_id = None
        orden_estado = None
        if faltante > 0:
            # Encolar orden de fabricación para el faltante y reflejarla en dashboard
            orchestrator = FabricacionOrchestrator(
                session=self.session,
                fabricacion_service=self.manufacturing_helper.fabricacion_service,
            )
            resultado_fabricacion = orchestrator.crear_orden(codigo, faltante)
            tiempo_estimado = resultado_fabricacion.get("tiempo_estimado", 0) or 0
            orden_id = resultado_fabricacion.get("id") if isinstance(resultado_fabricacion, dict) else None
            orden_estado = resultado_fabricacion.get("estado") if isinstance(resultado_fabricacion, dict) else None

        pedido = self._crear_pedido_venta(
            tipo="local",
            codigo=codigo,
            cantidad_solicitada=cantidad,
            cantidad_atendida=mover,
            cantidad_faltante=faltante,
            estado_destino="Reservado",
        )

        reservado_reg = self.repository.get_by_id((codigo, "Reservado"))
        return {
            "id_producto": codigo,
            "pedido_id": pedido.id if pedido else None,
            "cantidad_solicitada": cantidad,
            "cantidad_en_reserva": reservado_reg.cantidad if reservado_reg else 0,
            "faltante_fabricado": faltante,
            "tiempo_estimado": tiempo_estimado,
            "estado_destino": "Reservado",
            "orden_id": orden_id,
            "orden_estado": orden_estado,
            "estado_pedido": pedido.estado if pedido else "abierto",
        }

    def confirmar_retiro_local(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """Descuenta stock reservado cuando se retira en tienda."""
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser mayor a cero")
        reservado = self.repository.get_by_id((codigo, "Reservado"))
        if not reservado or reservado.cantidad < cantidad:
            raise ValueError("Cantidad insuficiente en Reservado para retirar")
        reservado.cantidad -= cantidad
        self.session.commit()
        self.session.refresh(reservado)
        return {
            "id_producto": codigo,
            "cantidad_retirada": cantidad,
            "reservado_restante": reservado.cantidad,
        }

    def list_pedidos(self, solo_abiertos: bool = False) -> list[PedidoVenta]:
        """Retorna pedidos de venta registrados (local/online)."""
        if solo_abiertos:
            return self.pedidos_repository.list_abiertos()
        return self.pedidos_repository.get_all()

    def hay_pedido_abierto(self, codigo: str, destino: str | None = None) -> bool:
        """True si existe algún pedido abierto para el producto (y opcionalmente el estado destino)."""
        pedidos = self.pedidos_repository.list_abiertos(codigo)
        if destino:
            destino_norm = normalize_estado(destino)
            return any(p.estado_destino == destino_norm for p in pedidos)
        return bool(pedidos)

    @staticmethod
    def _normalizar_totales_pedido(pedido: PedidoVenta) -> None:
        """Ajusta atendido/faltante para que nunca superen la solicitud ni queden negativos."""
        if not pedido:
            return
        pedido.cantidad_atendida = min(pedido.cantidad_atendida, pedido.cantidad_solicitada)
        pedido.cantidad_faltante = max(pedido.cantidad_solicitada - pedido.cantidad_atendida, 0)
        pedido.estado = "completado" if pedido.cantidad_faltante == 0 else "abierto"

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

    # === Deliveries / Ingresos dirigidos ===

    def ingresar_entrega_prioritaria(
        self,
        producto_id: str,
        cantidad: int,
        destino_preferido: str = "Pendiente",
    ) -> dict[str, Any]:
        """
        Ingresa productos a Disponible y luego intenta satisfacer pedidos completos
        (sin parciales). Si no hay pedidos abiertos, queda en Disponible.
        """
        codigo = normalize_producto_codigo(producto_id)

        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        self.incrementar(codigo, cantidad, estado="Disponible")
        self._satisfacer_pedidos_completos(codigo)
        destino_reg = self.repository.get_by_id((codigo, "Disponible"))

        return {
            "id_producto": codigo,
            "destino": "Disponible",
            "cantidad_ingresada": cantidad,
            "cantidad_final_en_destino": destino_reg.cantidad if destino_reg else 0,
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

    def _ensure_estado_registro(self, producto_id: str, estado: str) -> InventarioProducto:
        """Crea un registro de producto/estado con cantidad 0 si no existe."""
        registro = self.repository.get_by_id((producto_id, estado))
        if registro:
            return registro
        nuevo = InventarioProducto(id_producto=producto_id, estado=estado, cantidad=0)
        self.session.add(nuevo)
        self.session.commit()
        self.session.refresh(nuevo)
        return nuevo

    def _crear_pedido_venta(
        self,
        tipo: str,
        codigo: str,
        cantidad_solicitada: int,
        cantidad_atendida: int,
        cantidad_faltante: int,
        estado_destino: str,
    ) -> PedidoVenta:
        """Registra un pedido de venta para que las entregas se asignen al estado correcto."""
        estado = "abierto" if cantidad_faltante > 0 else "completado"
        destino = normalize_estado(estado_destino)
        codigo_normalizado = normalize_producto_codigo(codigo)
        pedido = self.pedidos_repository.create(
            tipo=tipo,
            id_producto=codigo_normalizado,
            cantidad_solicitada=cantidad_solicitada,
            cantidad_atendida=cantidad_atendida,
            cantidad_faltante=cantidad_faltante,
            estado_destino=destino,
            estado=estado,
        )
        # Si quedó completado desde el inicio, reflejar estado por si hay más movimientos
        if estado == "completado":
            self.session.commit()
        return pedido

    def _asignar_pedidos_abiertos(self, codigo: str) -> None:
        """
        Usa el stock disponible para cumplir pedidos de venta abiertos,
        moviendo al estado destino (Pendiente/Reservado) y cerrando el pedido.
        """
        pedidos = self.pedidos_repository.list_abiertos(codigo)
        if not pedidos:
            return

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0

        if disponible <= 0:
            return

        self.log.info("[ASIGNAR] %s tiene %s disponible para %s pedidos abiertos",
                      codigo, disponible, len(pedidos))

        for pedido in pedidos:
            if pedido.cantidad_faltante <= 0:
                pedido.estado = "completado"
                continue

            mover = min(disponible, pedido.cantidad_faltante)
            if mover <= 0:
                break

            self.log.info("[ASIGNAR] Pedido #%s: moviendo %s de Disponible → %s",
                         pedido.id, mover, pedido.estado_destino)

            # transferir mueve stock y valida registros destino
            self.transferir(codigo, "Disponible", pedido.estado_destino, mover)
            pedido.cantidad_faltante -= mover
            pedido.cantidad_atendida += mover

            # Validación: Nunca atender más de lo solicitado
            if pedido.cantidad_atendida > pedido.cantidad_solicitada:
                self.log.error(
                    "[ERROR] Pedido #%s: atendido=%s > solicitado=%s",
                    pedido.id, pedido.cantidad_atendida, pedido.cantidad_solicitada
                )
                raise ValueError(
                    f"Pedido #{pedido.id}: cantidad atendida excede solicitada"
                )

            if pedido.cantidad_faltante <= 0:
                pedido.estado = "completado"
                self.log.info("[ASIGNAR] Pedido #%s completado", pedido.id)

            # Actualizar variable local en lugar de refrescar DB
            disponible -= mover
            if disponible <= 0:
                break

        # Un solo commit al final
        self.session.commit()

    def _conciliar_pedidos_destino(
        self, codigo: str, destino: str, cantidad_incrementada: int
    ) -> None:
        """
        Si el ingreso fue directo al estado destino (Pendiente/Reservado),
        actualizar los pedidos abiertos para reflejar que ya se atendieron.
        """
        if cantidad_incrementada <= 0:
            return
        pedidos = self.pedidos_repository.list_abiertos(codigo)
        restante = cantidad_incrementada
        for pedido in pedidos:
            if pedido.estado_destino != destino:
                continue
            if pedido.cantidad_faltante <= 0:
                pedido.estado = "completado"
                continue
            asignar = min(restante, pedido.cantidad_faltante)
            if asignar <= 0:
                break
            pedido.cantidad_atendida += asignar
            pedido.cantidad_faltante -= asignar
            if pedido.cantidad_faltante <= 0:
                pedido.estado = "completado"
            restante -= asignar
            if restante <= 0:
                break
        self.session.commit()

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normaliza códigos de producto y estado en el payload."""
        payload["id_producto"] = normalize_producto_codigo(
            payload.get("id_producto", "")
        )
        payload["estado"] = normalize_estado(payload.get("estado", ""))
        return payload

    # === Overrides de flujo sin parciales (online/local) ===

    def _satisfacer_pedidos_completos(self, codigo: str) -> None:
        """
        Toma pedidos abiertos y los mueve al destino SOLO si hay stock suficiente
        para cubrir la cantidad solicitada completa. Procesa en orden FIFO.
        """
        pedidos = self.pedidos_repository.list_abiertos(codigo)
        if not pedidos:
            return
        pedidos.sort(key=lambda p: p.id)

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0
        if disponible <= 0:
            return

        for pedido in pedidos:
            self._normalizar_totales_pedido(pedido)
            requerido = pedido.cantidad_faltante
            if requerido <= 0:
                pedido.estado = "completado"
                continue
            if disponible >= requerido:
                # mover todo el pedido al destino final
                self.transferir(codigo, "Disponible", pedido.estado_destino, requerido)
                pedido.cantidad_atendida = pedido.cantidad_solicitada
                pedido.cantidad_faltante = 0
                pedido.estado = "completado"
                disponible -= requerido
                if disponible_reg:
                    disponible_reg.cantidad = disponible
            else:
                break

        self.session.commit()

    def ingresar_entrega_prioritaria(
        self,
        producto_id: str,
        cantidad: int,
        destino_preferido: str = "Pendiente",
    ) -> dict[str, Any]:
        """
        Ingresa productos a Disponible y luego intenta satisfacer pedidos completos.
        Ya no reparte parciales a Pendiente/Reservado.
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        self.incrementar(codigo, cantidad, estado="Disponible")
        self._satisfacer_pedidos_completos(codigo)
        destino_reg = self.repository.get_by_id((codigo, "Disponible"))

        return {
            "id_producto": codigo,
            "destino": "Disponible",
            "cantidad_ingresada": cantidad,
            "cantidad_final_en_destino": destino_reg.cantidad if destino_reg else 0,
        }

    def procesar_pedido_online(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Pedido online sin parciales:
        - Si hay stock completo: mover a A Despacho y cerrar.
        - Si falta stock: fabricar faltante; cuando Disponible cubra toda la orden, mover todo a Pendiente.
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser mayor a cero")

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0

        if disponible >= cantidad:
            self.transferir(codigo, "Disponible", "A Despacho", cantidad)
            pedido = self._crear_pedido_venta(
                tipo="online",
                codigo=codigo,
                cantidad_solicitada=cantidad,
                cantidad_atendida=cantidad,
                cantidad_faltante=0,
                estado_destino="A Despacho",
            )
            return {
                "id_producto": codigo,
                "pedido_id": pedido.id if pedido else None,
                "cantidad_solicitada": cantidad,
                "cantidad_en_pendiente": 0,
                "cantidad_inmediata": cantidad,
                "faltante_fabricado": 0,
                "tiempo_estimado": 0,
                "estado_destino": "A Despacho",
                "orden_id": None,
                "orden_estado": None,
                "estado_pedido": "completado",
            }

        faltante = cantidad - disponible
        orchestrator = FabricacionOrchestrator(
            session=self.session,
            fabricacion_service=self.manufacturing_helper.fabricacion_service,
        )
        resultado = orchestrator.crear_orden(codigo, faltante)
        tiempo_estimado = resultado.get("tiempo_estimado", 0) or 0
        orden_id = resultado.get("id") if isinstance(resultado, dict) else None
        orden_estado = resultado.get("estado") if isinstance(resultado, dict) else None

        pedido = self._crear_pedido_venta(
            tipo="online",
            codigo=codigo,
            cantidad_solicitada=cantidad,
            cantidad_atendida=0,
            cantidad_faltante=cantidad,
            estado_destino="Pendiente",
        )

        self._satisfacer_pedidos_completos(codigo)
        pendiente_reg = self.repository.get_by_id((codigo, "Pendiente"))
        return {
            "id_producto": codigo,
            "pedido_id": pedido.id if pedido else None,
            "cantidad_solicitada": cantidad,
            "cantidad_en_pendiente": pendiente_reg.cantidad if pendiente_reg else 0,
            "cantidad_inmediata": 0,
            "faltante_fabricado": faltante,
            "tiempo_estimado": tiempo_estimado,
            "estado_destino": "Pendiente",
            "orden_id": orden_id,
            "orden_estado": orden_estado,
            "estado_pedido": pedido.estado if pedido else "abierto",
        }

    def procesar_pedido_local(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Pedido local sin parciales:
        - Si hay stock completo: mover a Reservado y cerrar.
        - Si falta stock: fabricar faltante; cuando Disponible cubra toda la orden, mover todo a Reservado.
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser mayor a cero")

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0

        if disponible >= cantidad:
            self.transferir(codigo, "Disponible", "Reservado", cantidad)
            pedido = self._crear_pedido_venta(
                tipo="local",
                codigo=codigo,
                cantidad_solicitada=cantidad,
                cantidad_atendida=cantidad,
                cantidad_faltante=0,
                estado_destino="Reservado",
            )
            reservado_reg = self.repository.get_by_id((codigo, "Reservado"))
            return {
                "id_producto": codigo,
                "pedido_id": pedido.id if pedido else None,
                "cantidad_solicitada": cantidad,
                "cantidad_en_reserva": reservado_reg.cantidad if reservado_reg else 0,
                "faltante_fabricado": 0,
                "tiempo_estimado": 0,
                "estado_destino": "Reservado",
                "orden_id": None,
                "orden_estado": None,
                "estado_pedido": "completado",
            }

        faltante = cantidad - disponible
        orchestrator = FabricacionOrchestrator(
            session=self.session,
            fabricacion_service=self.manufacturing_helper.fabricacion_service,
        )
        resultado_fabricacion = orchestrator.crear_orden(codigo, faltante)
        tiempo_estimado = resultado_fabricacion.get("tiempo_estimado", 0) or 0
        orden_id = resultado_fabricacion.get("id") if isinstance(resultado_fabricacion, dict) else None
        orden_estado = resultado_fabricacion.get("estado") if isinstance(resultado_fabricacion, dict) else None

        pedido = self._crear_pedido_venta(
            tipo="local",
            codigo=codigo,
            cantidad_solicitada=cantidad,
            cantidad_atendida=0,
            cantidad_faltante=cantidad,
            estado_destino="Reservado",
        )

        self._satisfacer_pedidos_completos(codigo)

        reservado_reg = self.repository.get_by_id((codigo, "Reservado"))
        return {
            "id_producto": codigo,
            "pedido_id": pedido.id if pedido else None,
            "cantidad_solicitada": cantidad,
            "cantidad_en_reserva": reservado_reg.cantidad if reservado_reg else 0,
            "faltante_fabricado": faltante,
            "tiempo_estimado": tiempo_estimado,
            "estado_destino": "Reservado",
            "orden_id": orden_id,
            "orden_estado": orden_estado,
            "estado_pedido": pedido.estado if pedido else "abierto",
        }
