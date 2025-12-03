from .base_repository import BaseRepository
from ..models import InventarioProducto


class InventarioProductosRepository(BaseRepository):
    def __init__(self) -> None:
        super().__init__(InventarioProducto)
