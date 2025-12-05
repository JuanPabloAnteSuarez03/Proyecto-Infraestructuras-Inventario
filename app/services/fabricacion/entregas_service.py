import logging
from sqlalchemy.orm import Session
from app.models.entities import OrdenFabricacion


class EntregasFabricacionService:
    """Acumula entregas de fábrica sobre la orden más antigua elegible."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.log = logging.getLogger(self.__class__.__name__)

    def registrar_entrega(
        self,
        codigo: str,
        cantidad: int,
        estados_objetivo: tuple[str, ...] = ("esperando_fabricacion",),
    ) -> dict | None:
        orden = (
            self.session.query(OrdenFabricacion)
            .filter(
                OrdenFabricacion.id_producto == codigo.upper(),
                OrdenFabricacion.estado.in_(estados_objetivo),
            )
            .order_by(
                OrdenFabricacion.cantidad.asc(),
                OrdenFabricacion.id.asc(),
            )
            .with_for_update()
            .first()
        )

        if not orden:
            self.log.info(
                "[INGRESO] No hay orden elegible para %s en estados %s",
                codigo,
                estados_objetivo,
            )
            return None

        detalle = orden.detalle if isinstance(orden.detalle, dict) else {}
        entrega_acumulada = detalle.get("entrega_acumulada", 0) + cantidad
        orden.detalle = {**detalle, "entrega_acumulada": entrega_acumulada}

        if orden.estado in ("confirmado", "consumiendo_piezas") and "esperando_fabricacion" in estados_objetivo:
            orden.estado = "esperando_fabricacion"

        completada = entrega_acumulada >= orden.cantidad
        if completada:
            orden.estado = "completada"

        self.session.commit()

        if completada:
            self.log.info(
                "[INGRESO] ✓ Orden #%s completada: pedido %s, recibido total %s (última entrega %s)",
                orden.id,
                orden.cantidad,
                entrega_acumulada,
                cantidad,
            )
        else:
            self.log.info(
                "[INGRESO] Entrega parcial orden #%s: recibido %s, acumulado %s/%s",
                orden.id,
                cantidad,
                entrega_acumulada,
                orden.cantidad,
            )

        return {
            "orden": orden,
            "acumulado": entrega_acumulada,
            "completada": completada,
        }
