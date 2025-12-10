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

    Maneja productos en cuatro estados:
      - Disponible
      - Reservado
      - Pendiente
      - A Despacho

    Flujos clave de VENTAS:

    LOCAL (tienda)
    ---------------

    1) Guardar pendiente (venta local):
       - Stock suficiente: Disponible -> Reservado (por el total)
       - Stock insuficiente: Disponible -> Reservado (parcial) y se fabrica el faltante.
         Lo fabricado entra a Disponible y se auto-mueve a Reservado solo cuando
         hay stock suficiente para completar el pedido (vía _satisfacer_pedidos_completos).

    2) Finalizar venta (tienda) CON reserva:
       - Descuenta siempre desde Reservado (y si falta, de Disponible).

    3) Finalizar venta DIRECTA (tienda) SIN haber hecho "Guardar pendiente":
       - Stock suficiente: descuenta directamente desde Disponible.
       - Stock insuficiente: NO reserva nada. Se crea un PedidoVenta local
         cuyo destino es Disponible. Cuando el stock Disponible alcanza la
         cantidad del pedido, se descuenta automáticamente desde Disponible.

    ONLINE (domicilio)
    -------------------

    4) Guardar pendiente (venta online):
       - Stock suficiente: Disponible -> Reservado (por el total)
       - Stock insuficiente: Disponible -> Reservado (parcial) y se fabrica el faltante.
         Lo fabricado queda en Disponible, NO se auto-asigna a ningún otro estado.

    5) Finalizar venta (domicilio) CON reserva (hubo "Guardar pendiente"):
       - Caso con reserva completa: Reservado -> A Despacho (cantidad pedida)
       - Caso de faltantes (mezcla Reservado + Disponible):
             Reservado (lo que haya) + Disponible (restante)
             -> todo el pedido se mueve a Pendiente
         quedando:
             cantidad_pedida en Pendiente
             y cualquier extra en Disponible.

    6) Finalizar venta DIRECTA (domicilio) SIN haber hecho "Guardar pendiente":
       - Stock suficiente: Disponible -> A Despacho (directo, sin pasar por Reservado).
       - Stock insuficiente: Disponible -> Pendiente (lo que haya),
         se fabrica el faltante y también se lleva a Pendiente, de modo que
         todo el pedido quede concentrado en Pendiente.
    """

    def __init__(
        self,
        session: Session,
        repository: InventarioProductosRepository | None = None,
        piezas_repository: InventarioPiezasRepository | None = None,
        pedidos_repository: PedidoVentaRepository | None = None,
    ) -> None:
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

    # ============================================================
    # CRUD / utilidades básicas
    # ============================================================

    def list(self) -> list[InventarioProducto]:
        return self.repository.get_all()

    def list_by_estado(self, estado: str) -> list[InventarioProducto]:
        estado_normalizado = normalize_estado(estado)
        return (
            self.session.query(InventarioProducto)
            .filter_by(estado=estado_normalizado)
            .order_by(InventarioProducto.id_producto)
            .all()
        )

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

    def update(
        self, producto_id: str, estado: str, payload: dict[str, Any]
    ) -> InventarioProducto | None:
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado)
        payload = {k: v for k, v in payload.items() if k == "cantidad"}
        return self.repository.update((codigo, estado_normalizado), **payload)

    def delete(self, producto_id: str, estado: str) -> bool:
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado)
        return self.repository.delete((codigo, estado_normalizado))

    def reset_all(self) -> int:
        """
        Resetea todas las cantidades de productos a cero.
        """
        updated = self.session.query(InventarioProducto).update({"cantidad": 0})
        self.session.commit()
        return updated

    def reset_pedidos(self) -> int:
        """
        Elimina todos los pedidos de venta (online y local).
        """
        deleted = self.session.query(PedidoVenta).delete(synchronize_session=False)
        self.session.commit()
        return deleted

    def descontar_estado(
        self, producto_id: str, estado: str, cantidad: int
    ) -> InventarioProducto:
        """
        Descuenta cantidad de un estado específico (Pendiente, A Despacho, etc.).
        Lanza error si no existe el registro o si no hay stock suficiente.
        """
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado)

        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        registro = self.repository.get_by_id((codigo, estado_normalizado))
        if not registro:
            raise ValueError("Producto no encontrado en el estado solicitado")
        if registro.cantidad < cantidad:
            raise ValueError("Cantidad insuficiente en el estado solicitado")

        registro.cantidad -= cantidad
        self.session.commit()
        self.session.refresh(registro)
        return registro

    # ============================================================
    # Operaciones de inventario básico
    # ============================================================

    def incrementar(
        self, producto_id: str, cantidad: int, estado: str | None = None
    ) -> InventarioProducto:
        """
        Incrementa la cantidad de un producto en un estado específico.

        Si el registro no existe, lo crea.
        Si el estado es Disponible:
        - intenta completar pedidos LOCALES abiertos (no online)
          moviendo de Disponible -> estado_destino del pedido,
          pero solo si se puede cubrir el pedido completo.
        """
        codigo = normalize_producto_codigo(producto_id)
        estado_normalizado = normalize_estado(estado or "Disponible")

        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

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
            # Solo auto-asignar a pedidos LOCAL (no online)
            self._satisfacer_pedidos_completos(codigo)
            actualizado = self.repository.get_by_id((codigo, estado_normalizado))
            if actualizado:
                resultado = actualizado

        return resultado

    def transferir(
        self, producto_id: str, estado_origen: str, estado_destino: str, cantidad: int
    ) -> list[InventarioProducto]:
        """
        Transfiere productos entre estados (Disponible, Reservado, Pendiente, A Despacho).
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

    # ============================================================
    # VENTAS – Guardar pendiente
    # ============================================================

    def procesar_pedido_local(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Venta LOCAL (método de entrega: TIENDA) al presionar *Guardar pendiente*.

        - Stock suficiente:
            Disponible -> Reservado (por el total pedido).

        - Stock insuficiente:
            Disponible -> Reservado (hasta donde alcance) y
            se fabrica el faltante. Lo fabricado entra a Disponible
            y luego se auto-mueve a Reservado cuando haya stock suficiente
            para completar el pedido (vía _satisfacer_pedidos_completos).
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0

        mover = min(disponible, cantidad)
        faltante = max(cantidad - mover, 0)

        # 1) Reservar lo que se pueda
        if mover > 0:
            self.transferir(codigo, "Disponible", "Reservado", mover)

        # 2) Fabricar faltante si es necesario
        tiempo_estimado = 0
        orden_id = None
        orden_estado = None
        if faltante > 0:
            orchestrator = FabricacionOrchestrator(
                session=self.session,
                fabricacion_service=self.manufacturing_helper.fabricacion_service,
            )
            resultado_fabricacion = orchestrator.crear_orden(codigo, faltante)
            tiempo_estimado = resultado_fabricacion.get("tiempo_estimado", 0) or 0
            orden_id = (
                resultado_fabricacion.get("id")
                if isinstance(resultado_fabricacion, dict)
                else None
            )
            orden_estado = (
                resultado_fabricacion.get("estado")
                if isinstance(resultado_fabricacion, dict)
                else None
            )

        # Registrar pedido ligado a estado destino RESERVADO
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

    def procesar_pedido_online(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Venta ONLINE (método de entrega: DOMICILIO) al presionar *Guardar pendiente*.

        - Stock suficiente:
            Disponible -> Reservado (queda todo reservado).

        - Stock insuficiente:
            Disponible -> Reservado (hasta donde alcance) y
            se fabrica el faltante. Lo fabricado queda en Disponible
            sin auto-moverse (los pedidos ONLINE se ignoran en
            _satisfacer_pedidos_completos).
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0

        mover = min(disponible, cantidad)
        faltante = max(cantidad - mover, 0)

        # 1) Reservar lo que se pueda
        if mover > 0:
            self.transferir(codigo, "Disponible", "Reservado", mover)

        # 2) Fabricar faltante si hace falta
        tiempo_estimado = 0
        orden_id = None
        orden_estado = None
        if faltante > 0:
            orchestrator = FabricacionOrchestrator(
                session=self.session,
                fabricacion_service=self.manufacturing_helper.fabricacion_service,
            )
            resultado = orchestrator.crear_orden(codigo, faltante)
            tiempo_estimado = resultado.get("tiempo_estimado", 0) or 0
            orden_id = resultado.get("id") if isinstance(resultado, dict) else None
            orden_estado = (
                resultado.get("estado") if isinstance(resultado, dict) else None
            )

        # Registramos el pedido como ONLINE, destino lógico final "Pendiente"
        pedido = self._crear_pedido_venta(
            tipo="online",
            codigo=codigo,
            cantidad_solicitada=cantidad,
            cantidad_atendida=mover,
            cantidad_faltante=faltante,
            estado_destino="Pendiente",
        )

        reservado_reg = self.repository.get_by_id((codigo, "Reservado"))
        return {
            "id_producto": codigo,
            "pedido_id": pedido.id if pedido else None,
            "cantidad_solicitada": cantidad,
            "cantidad_en_reserva": reservado_reg.cantidad if reservado_reg else 0,
            "faltante_fabricado": faltante,
            "tiempo_estimado": tiempo_estimado,
            "estado_destino": "Pendiente",
            "orden_id": orden_id,
            "orden_estado": orden_estado,
            "estado_pedido": pedido.estado if pedido else "abierto",
        }

    # ============================================================
    # VENTAS – Finalizar venta (router ÚNICO para el frontend)
    # ============================================================

    def confirmar_retiro(
        self, producto_id: str, cantidad: int, metodo_entrega: str | None = "tienda"
    ) -> dict[str, Any]:
        """
        Finalizar venta (botón *Finalizar venta* en el frontend).

        - Si YA hubo "Guardar pendiente" (es decir, hay stock en RESERVADO),
          usa los flujos clásicos:
            * tienda    -> confirmar_retiro_local
            * domicilio -> preparar_despacho_domicilio

        - Si NO hubo "Guardar pendiente" (no hay nada en Reservado para el producto),
          se considera FINALIZAR VENTA DIRECTA:
            * tienda    -> _finalizar_directo_tienda
            * domicilio -> _finalizar_directo_domicilio

        Importante:
        - NO usamos el estado Pendiente para decidir si hubo o no "Guardar pendiente",
          porque Pendiente también se utiliza en ventas DIRECTAS a domicilio.
        """
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        codigo = normalize_producto_codigo(producto_id)

        metodo = (metodo_entrega or "tienda").strip().lower()
        metodo = {
            "pickup": "tienda",
            "store": "tienda",
            "local": "tienda",
            "tienda": "tienda",
            "dispatch": "domicilio",
            "delivery": "domicilio",
            "envio": "domicilio",
            "domicilio": "domicilio",
        }.get(metodo, metodo)

        # --- Detectar si existe contexto de "Guardar pendiente" previo ---
        reservado = self.repository.get_by_id((codigo, "Reservado"))
        reservado_cant = reservado.cantidad if reservado else 0

        hay_reserva = reservado_cant > 0

        # --- Rutas según método de entrega y si hay o no reserva ---
        if metodo == "tienda":
            if hay_reserva:
                # Flujo clásico: confirmar retiro usando Reservado (+Disponible)
                return self.confirmar_retiro_local(producto_id, cantidad)
            else:
                # Flujo DIRECTO tienda: solo Disponible
                disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
                disponible = disponible_reg.cantidad if disponible_reg else 0
                return self._finalizar_directo_tienda(
                    codigo, cantidad, disponible, disponible_reg
                )

        if metodo == "domicilio":
            if hay_reserva:
                # Flujo clásico (viene de Guardar pendiente: Reservado + Disponible)
                return self.preparar_despacho_domicilio(producto_id, cantidad)
            else:
                # Flujo DIRECTO domicilio: solo Disponible
                disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
                disponible = disponible_reg.cantidad if disponible_reg else 0
                return self._finalizar_directo_domicilio(
                    codigo, cantidad, disponible, disponible_reg
                )

        raise ValueError("Método de entrega no permitido. Use tienda o domicilio.")

    # ============================================================
    # VENTAS – Finalizar venta (CON reserva existente)
    # ============================================================

    def confirmar_retiro_local(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Finalizar venta LOCAL (retiro en tienda) CUANDO YA HAY RESERVA.

        Descuenta SIEMPRE desde Reservado en la medida de lo posible
        y solo si falta, utiliza Disponible.
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        reservado = self.repository.get_by_id((codigo, "Reservado"))
        disponible = self.repository.get_by_id((codigo, "Disponible"))
        reservado_cant = reservado.cantidad if reservado else 0
        disponible_cant = disponible.cantidad if disponible else 0

        total_disponible = reservado_cant + disponible_cant
        if total_disponible < cantidad:
            raise ValueError("Cantidad insuficiente para retirar")

        restante = cantidad

        # Consumir primero de Reservado
        if reservado_cant > 0:
            usar_reservado = min(restante, reservado_cant)
            reservado.cantidad -= usar_reservado
            restante -= usar_reservado

        # Si aún falta, consumir de Disponible
        if restante > 0:
            if not disponible or disponible.cantidad < restante:
                raise ValueError("Cantidad insuficiente para retirar")
            disponible.cantidad -= restante

        self.session.commit()
        return {
            "id_producto": codigo,
            "cantidad_retirada": cantidad,
            "reservado_restante": reservado.cantidad if reservado else 0,
            "disponible_restante": disponible.cantidad if disponible else 0,
        }

    def preparar_despacho_domicilio(
        self, producto_id: str, cantidad: int
    ) -> dict[str, Any]:
        """
        Finalizar venta ONLINE (despacho a domicilio) CUANDO YA HAY RESERVA
        (es decir, la venta vino de *Guardar pendiente*).

        Dos flujos independientes:

        1) STOCK INSUFICIENTE (caso de faltantes):
           - Al guardar pendiente se reservó lo disponible (Disponible -> Reservado)
             y se fabricó el faltante, que terminó en Disponible.
           - Al finalizar, se toma lo que esté en Reservado + lo necesario de
             Disponible y se mueve TODO el pedido al estado Pendiente:

             Resultado esperado:
                cantidad_pedida en Pendiente
                extra (si lo hubo) en Disponible

        2) STOCK SUFICIENTE EN RESERVADO:
           - Al guardar pendiente se movió todo a Reservado.
           - Al finalizar, se mueve la cantidad pedida de Reservado -> A Despacho.

        Además:
        - Si NO hay nada en Reservado pero sí hay stock suficiente en Disponible
          y el frontend llama directamente aquí, se interpreta como flujo directo
          y se hace Disponible -> A Despacho.
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        reservado = self.repository.get_by_id((codigo, "Reservado"))
        disponible = self.repository.get_by_id((codigo, "Disponible"))
        pendiente = self._ensure_estado_registro(codigo, "Pendiente")
        despacho_dest = self._ensure_estado_registro(codigo, "A Despacho")

        reservado_cant = reservado.cantidad if reservado else 0
        disponible_cant = disponible.cantidad if disponible else 0
        total = reservado_cant + disponible_cant

        if total < cantidad:
            raise ValueError(
                "Cantidad insuficiente para preparar despacho a domicilio. "
                f"Reservado={reservado_cant}, Disponible={disponible_cant}, solicitado={cantidad}"
            )

        # --- CASO ESPECIAL: sin reserva pero stock suficiente en Disponible ---
        if reservado_cant == 0 and disponible_cant >= cantidad:
            self.transferir(codigo, "Disponible", "A Despacho", cantidad)

            # Refrescar para respuesta
            disponible = self.repository.get_by_id((codigo, "Disponible"))
            pendiente = self.repository.get_by_id((codigo, "Pendiente"))
            despacho_dest = self.repository.get_by_id((codigo, "A Despacho"))

            return {
                "id_producto": codigo,
                "metodo_entrega": "domicilio",
                "cantidad_preparada": cantidad,
                "estado_destino": "A Despacho",
                "despacho_total": despacho_dest.cantidad if despacho_dest else 0,
                "pendiente_total": pendiente.cantidad if pendiente else 0,
                "movido_desde_reservado": 0,
                "movido_desde_pendiente": 0,
                "movido_desde_disponible": cantidad,
                "faltante_fabricado": 0,
                "reservado_restante": 0,
                "pendiente_restante": pendiente.cantidad if pendiente else 0,
                "despacho_restante": despacho_dest.cantidad if despacho_dest else 0,
                "disponible_restante": disponible.cantidad if disponible else 0,
                "tiempo_estimado": 0,
            }

        movidos = {"reservado": 0, "pendiente": 0, "disponible": 0}
        tiempo_estimado = 0
        faltante_fabricado = 0  # solo informativo aquí

        # --- Flujo 2: stock suficiente en Reservado -> A Despacho directamente
        if reservado_cant >= cantidad:
            self.transferir(codigo, "Reservado", "A Despacho", cantidad)
            movidos["reservado"] = cantidad
            estado_destino = "A Despacho"

        # --- Flujo 1: mezcla Reservado + Disponible -> Pendiente
        else:
            usar_res = reservado_cant
            if usar_res > 0:
                self.transferir(codigo, "Reservado", "Pendiente", usar_res)
                movidos["reservado"] = usar_res

            faltante = cantidad - usar_res
            if disponible_cant < faltante:
                # No debería ocurrir porque total >= cantidad, pero se valida.
                raise ValueError(
                    "Disponible insuficiente para completar movimiento a Pendiente"
                )

            self.transferir(codigo, "Disponible", "Pendiente", faltante)
            movidos["disponible"] = faltante
            estado_destino = "Pendiente"

        # Refrescar cantidades para la respuesta
        reservado = self.repository.get_by_id((codigo, "Reservado"))
        disponible = self.repository.get_by_id((codigo, "Disponible"))
        pendiente = self.repository.get_by_id((codigo, "Pendiente"))
        despacho_dest = self.repository.get_by_id((codigo, "A Despacho"))

        return {
            "id_producto": codigo,
            "metodo_entrega": "domicilio",
            "cantidad_preparada": cantidad,
            "estado_destino": estado_destino,
            "despacho_total": despacho_dest.cantidad if despacho_dest else 0,
            "pendiente_total": pendiente.cantidad if pendiente else 0,
            "movido_desde_reservado": movidos["reservado"],
            "movido_desde_pendiente": movidos["pendiente"],
            "movido_desde_disponible": movidos["disponible"],
            "faltante_fabricado": faltante_fabricado,
            "reservado_restante": reservado.cantidad if reservado else 0,
            "pendiente_restante": pendiente.cantidad if pendiente else 0,
            "despacho_restante": despacho_dest.cantidad if despacho_dest else 0,
            "disponible_restante": disponible.cantidad if disponible else 0,
            "tiempo_estimado": tiempo_estimado,
        }

    # ============================================================
    # VENTAS – Finalizar venta DIRECTA (sin haber guardado pendiente)
    # ============================================================

    def finalizar_venta_directa(
        self, producto_id: str, cantidad: int, metodo_entrega: str | None = "tienda"
    ) -> dict[str, Any]:
        """
        Método explícito para FINALIZAR VENTA DIRECTA, sin haber pasado por
        'Guardar pendiente'. (El frontend puede llamarlo directamente si quiere.)

        Internamente hace lo mismo que confirmar_retiro cuando detecta
        que no hay reservas.
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

        metodo = (metodo_entrega or "tienda").strip().lower()
        metodo = {
            "pickup": "tienda",
            "store": "tienda",
            "local": "tienda",
            "tienda": "tienda",
            "dispatch": "domicilio",
            "delivery": "domicilio",
            "envio": "domicilio",
            "domicilio": "domicilio",
        }.get(metodo, metodo)

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0

        if metodo == "tienda":
            return self._finalizar_directo_tienda(
                codigo, cantidad, disponible, disponible_reg
            )
        if metodo == "domicilio":
            return self._finalizar_directo_domicilio(
                codigo, cantidad, disponible, disponible_reg
            )

        raise ValueError("Método de entrega no permitido. Use tienda o domicilio.")

    def _finalizar_directo_tienda(
        self,
        codigo: str,
        cantidad: int,
        disponible: int,
        disponible_reg: InventarioProducto | None,
    ) -> dict[str, Any]:
        """
        Caso DIRECTO: venta local (tienda) sin pasar por Guardar pendiente.

        - Stock suficiente: descuenta directamente desde Disponible.
        - Stock insuficiente: NO se mueve nada a Reservado. Se crea un
          PedidoVenta local cuyo destino es Disponible, y cuando el stock
          Disponible alcance la cantidad pedida, se descuenta directamente
          desde Disponible (vía _satisfacer_pedidos_completos).
        """

        # === Caso 1: STOCK SUFICIENTE -> descuenta solo de Disponible ===
        if disponible >= cantidad:
            if not disponible_reg:
                raise ValueError(
                    "No existe registro Disponible para el producto en inventario"
                )
            if disponible_reg.cantidad < cantidad:
                raise ValueError("Cantidad insuficiente en Disponible para retirar")

            disponible_reg.cantidad -= cantidad
            self.session.commit()
            self.session.refresh(disponible_reg)

            return {
                "id_producto": codigo,
                "metodo_entrega": "tienda",
                "modo": "directo",
                "cantidad_retirada": cantidad,
                "reservado_restante": 0,
                "disponible_restante": disponible_reg.cantidad,
                "pedido_id": None,
                "estado_pedido": "completado",
                "faltante_fabricado": 0,
                "tiempo_estimado": 0,
            }

        # === Caso 2: STOCK INSUFICIENTE ===
        # No movemos nada a Reservado. Todo el pedido queda "esperando" en Disponible.
        faltante = max(cantidad - disponible, 0)

        tiempo_estimado = 0
        orden_id = None
        orden_estado = None
        if faltante > 0:
            orchestrator = FabricacionOrchestrator(
                session=self.session,
                fabricacion_service=self.manufacturing_helper.fabricacion_service,
            )
            resultado_fabricacion = orchestrator.crear_orden(codigo, faltante)
            tiempo_estimado = resultado_fabricacion.get("tiempo_estimado", 0) or 0
            orden_id = (
                resultado_fabricacion.get("id")
                if isinstance(resultado_fabricacion, dict)
                else None
            )
            orden_estado = (
                resultado_fabricacion.get("estado")
                if isinstance(resultado_fabricacion, dict)
                else None
            )

        # Pedido local cuyo destino es "Disponible": cuando haya stock suficiente
        # se descontará directamente desde Disponible (sin pasar por Reservado).
        pedido = self._crear_pedido_venta(
            tipo="local",
            codigo=codigo,
            cantidad_solicitada=cantidad,
            cantidad_atendida=0,        # nada atendido todavía
            cantidad_faltante=cantidad,  # todo el pedido pendiente
            estado_destino="Disponible",
        )

        # Intentamos satisfacer por si, excepcionalmente, ya hubiera stock suficiente
        self._satisfacer_pedidos_completos(codigo)

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))

        return {
            "id_producto": codigo,
            "metodo_entrega": "tienda",
            "modo": "directo",
            "cantidad_solicitada": cantidad,
            "cantidad_en_reserva": 0,
            "cantidad_inmediata": 0,
            "faltante_fabricado": faltante,
            "tiempo_estimado": tiempo_estimado,
            "pedido_id": pedido.id if pedido else None,
            "estado_pedido": pedido.estado if pedido else "abierto",
            "orden_id": orden_id,
            "orden_estado": orden_estado,
            "disponible_restante": disponible_reg.cantidad if disponible_reg else 0,
        }

    def _finalizar_directo_domicilio(
        self,
        codigo: str,
        cantidad: int,
        disponible: int,
        disponible_reg: InventarioProducto | None,
    ) -> dict[str, Any]:
        """
        Caso DIRECTO: venta online (domicilio) sin pasar por Guardar pendiente.

        - Stock suficiente: Disponible -> A Despacho directo.
        - Stock insuficiente:
              * Mover TODO lo que haya en Disponible -> Pendiente.
              * Fabricar el faltante y dejarlo también en Pendiente, de modo que
                todo el pedido quede concentrado en Pendiente.
        """

        # === Caso 3: STOCK SUFICIENTE -> Disponible -> A Despacho directo ===
        if disponible >= cantidad:
            self.transferir(codigo, "Disponible", "A Despacho", cantidad)
            despacho_reg = self.repository.get_by_id((codigo, "A Despacho"))

            pedido = self._crear_pedido_venta(
                tipo="online",
                codigo=codigo,
                cantidad_solicitada=cantidad,
                cantidad_atendida=cantidad,
                cantidad_faltante=0,
                estado_destino="A Despacho",
            )

            disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
            return {
                "id_producto": codigo,
                "metodo_entrega": "domicilio",
                "modo": "directo",
                "cantidad_solicitada": cantidad,
                "cantidad_inmediata": cantidad,
                "cantidad_en_pendiente": 0,
                "faltante_fabricado": 0,
                "tiempo_estimado": 0,
                "estado_destino": "A Despacho",
                "pedido_id": pedido.id if pedido else None,
                "estado_pedido": pedido.estado if pedido else "completado",
                "despacho_total": despacho_reg.cantidad if despacho_reg else 0,
                "disponible_restante": (
                    disponible_reg.cantidad if disponible_reg else 0
                ),
            }

        # === Caso 4: STOCK INSUFICIENTE ===
        # 1) Mover TODO lo que haya a Pendiente
        mover = max(min(disponible, cantidad), 0)
        faltante = cantidad - mover  # lo que hay que fabricar

        if mover > 0:
            self.transferir(codigo, "Disponible", "Pendiente", mover)

        # 2) Fabricar el faltante y llevarlo también a Pendiente
        tiempo_estimado = 0

        if faltante > 0:
            # Ingreso personalizado: todo lo fabricado entra a PENDIENTE
            def _ingresar_en_pendiente(
                prod_id: str,
                qty: int,
                estado: str | None = None,
            ) -> InventarioProducto:
                # ignoramos el estado que venga y forzamos "Pendiente"
                return self.incrementar(prod_id, qty, estado="Pendiente")

            resultado_fabricacion = self.manufacturing_helper.producir_lote(
                codigo,
                faltante,
                _ingresar_en_pendiente,
            )
            tiempo_estimado = resultado_fabricacion.get("tiempo_total", 0) or 0

        # En este punto todo el pedido (mover + faltante) terminó en Pendiente
        pendiente_reg = self.repository.get_by_id((codigo, "Pendiente"))
        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))

        # Como ya fabricamos el faltante, el pedido queda completamente atendido
        pedido = self._crear_pedido_venta(
            tipo="online",
            codigo=codigo,
            cantidad_solicitada=cantidad,
            cantidad_atendida=cantidad,
            cantidad_faltante=0,
            estado_destino="Pendiente",
        )

        return {
            "id_producto": codigo,
            "metodo_entrega": "domicilio",
            "modo": "directo",
            "cantidad_solicitada": cantidad,
            "cantidad_en_pendiente": pendiente_reg.cantidad if pendiente_reg else 0,
            "cantidad_inmediata": mover,
            "faltante_fabricado": faltante,
            "tiempo_estimado": tiempo_estimado,
            "estado_destino": "Pendiente",
            "pedido_id": pedido.id if pedido else None,
            "estado_pedido": pedido.estado if pedido else "completado",
            "orden_id": None,
            "orden_estado": None,
            "disponible_restante": (
                disponible_reg.cantidad if disponible_reg else 0
            ),
        }

    # ============================================================
    # Otras APIs de dominio (compatibilidad)
    # ============================================================

    def reservar_para_venta(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        API genérica de reserva (no usada directamente por los flujos
        específicos de Guardar pendiente / Finalizar, pero se mantiene
        para compatibilidad).
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

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
        Despacha productos para entrega (API genérica).
        """
        codigo = normalize_producto_codigo(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")

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

    # ============================================================
    # Pedidos de venta
    # ============================================================

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
        pedido.cantidad_atendida = min(
            pedido.cantidad_atendida, pedido.cantidad_solicitada
        )
        pedido.cantidad_faltante = max(
            pedido.cantidad_solicitada - pedido.cantidad_atendida, 0
        )
        pedido.estado = "completado" if pedido.cantidad_faltante == 0 else "abierto"

    # ============================================================
    # Fabricación / reposición
    # ============================================================

    def fabricar_productos(self, producto_id: str, cantidad: int) -> dict[str, Any]:
        """
        Fabrica productos y los agrega al inventario disponible.
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

    def ingresar_entrega_prioritaria(
        self,
        producto_id: str,
        cantidad: int,
        destino_preferido: str = "Pendiente",
    ) -> dict[str, Any]:
        """
        Ingresa productos a Disponible y luego intenta satisfacer pedidos LOCAL
        completos (sin parciales). Si no hay pedidos abiertos, queda en Disponible.
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

    # ============================================================
    # Helpers internos
    # ============================================================

    def _producir_para_venta(self, codigo: str, cantidad: int) -> dict[str, Any]:
        """Produce un lote para cumplir con una venta."""
        return self.manufacturing_helper.producir_lote(
            codigo, cantidad, self.incrementar
        )

    def _evaluar_stock_minimo(self, producto_id: str) -> dict[str, int]:
        """
        Evalúa si el stock está por debajo del mínimo.
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
                resultado.get("estado") if isinstance(resultado, dict) else None,
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
        if estado == "completado":
            self.session.commit()
        return pedido

    def _asignar_pedidos_abiertos(self, codigo: str) -> None:
        """
        Versión antigua que permitía parciales; se mantiene para compatibilidad
        de API interna, pero NO se usa en los nuevos flujos.
        """
        pedidos = self.pedidos_repository.list_abiertos(codigo)
        if not pedidos:
            return

        disponible_reg = self.repository.get_by_id((codigo, "Disponible"))
        disponible = disponible_reg.cantidad if disponible_reg else 0

        if disponible <= 0:
            return

        for pedido in pedidos:
            if pedido.cantidad_faltante <= 0:
                pedido.estado = "completado"
                continue

            mover = min(disponible, pedido.cantidad_faltante)
            if mover <= 0:
                break

            self.transferir(codigo, "Disponible", pedido.estado_destino, mover)
            pedido.cantidad_faltante -= mover
            pedido.cantidad_atendida += mover

            if pedido.cantidad_atendida > pedido.cantidad_solicitada:
                raise ValueError(
                    f"Pedido #{pedido.id}: cantidad atendida excede solicitada"
                )

            if pedido.cantidad_faltante <= 0:
                pedido.estado = "completado"

            disponible -= mover
            if disponible <= 0:
                break

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

    # ============================================================
    # Regla clave de auto-asignación LOCAL
    # ============================================================

    def _satisfacer_pedidos_completos(self, codigo: str) -> None:
        """
        Toma PEDIDOS LOCALES abiertos y los mueve al destino SOLO si hay stock
        suficiente para cubrir la cantidad solicitada completa. Procesa en orden FIFO.

        Importante: los pedidos ONLINE se ignoran aquí para no interferir con los
        flujos de Guardar pendiente / Finalizar venta de domicilio.

        Soporta dos tipos de destino:
        - "Reservado": mueve Disponible -> Reservado.
        - "Disponible": descuenta directamente desde Disponible (venta directa
          tienda con stock insuficiente).
        """
        pedidos = [
            p
            for p in self.pedidos_repository.list_abiertos(codigo)
            if getattr(p, "tipo", None) == "local"
        ]
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

            # Solo atendemos pedidos COMPLETOS
            if disponible < requerido:
                break

            destino = pedido.estado_destino  # ya viene normalizado desde _crear_pedido_venta

            if destino == "Disponible":
                # Consumo directo desde Disponible (no se mueve a otro estado)
                if not disponible_reg or disponible_reg.cantidad < requerido:
                    raise ValueError(
                        f"Stock disponible inconsistente al cerrar pedido #{pedido.id}"
                    )
                disponible_reg.cantidad -= requerido
                disponible -= requerido
            else:
                # Caso clásico: Disponible -> estado_destino (ej: Reservado)
                self.transferir(codigo, "Disponible", destino, requerido)
                disponible -= requerido
                if disponible_reg:
                    # reflejar el valor actualizado
                    disponible_reg.cantidad = disponible

            pedido.cantidad_atendida = pedido.cantidad_solicitada
            pedido.cantidad_faltante = 0
            pedido.estado = "completado"

        self.session.commit()
