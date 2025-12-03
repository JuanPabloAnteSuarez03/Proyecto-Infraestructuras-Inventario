from .base_repository import BaseRepository
from ..models import SolicitudPieza


class SolicitudPiezaRepository(BaseRepository):
    def __init__(self) -> None:
        super().__init__(SolicitudPieza)
