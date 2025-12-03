from .base_repository import BaseRepository
from ..models import InventarioPieza


class InventarioPiezasRepository(BaseRepository):
    def __init__(self) -> None:
        super().__init__(InventarioPieza)
