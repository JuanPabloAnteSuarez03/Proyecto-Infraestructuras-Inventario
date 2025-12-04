from sqlalchemy.orm import Session
from .base_repository import BaseRepository
from ..models import InventarioPieza


class InventarioPiezasRepository(BaseRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(InventarioPieza, session)
