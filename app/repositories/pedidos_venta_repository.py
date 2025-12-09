from sqlalchemy.orm import Session
from .base_repository import BaseRepository
from ..models import PedidoVenta


class PedidoVentaRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(PedidoVenta, session)

    def list_abiertos(self, codigo: str | None = None) -> list[PedidoVenta]:
        query = (
            self.session.query(PedidoVenta)
            .filter(PedidoVenta.estado == "abierto")
            .order_by(PedidoVenta.id.asc())
        )
        if codigo:
            query = query.filter(PedidoVenta.id_producto == codigo)
        return query.all()
