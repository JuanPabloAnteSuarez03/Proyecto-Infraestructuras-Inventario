from .base_repository import BaseRepository
from ..models import Movimiento


class MovimientosRepository(BaseRepository):
    def __init__(self) -> None:
        super().__init__(Movimiento)
