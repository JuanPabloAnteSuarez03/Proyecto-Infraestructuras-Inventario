from .base_repository import BaseRepository
from ..models import OrdenFabricacion


class OrdenFabricacionRepository(BaseRepository):
    def __init__(self) -> None:
        super().__init__(OrdenFabricacion)
