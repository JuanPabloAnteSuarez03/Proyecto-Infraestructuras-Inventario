from .base_repository import BaseRepository
from ..models import Proveedor


class ProveedoresRepository(BaseRepository):
    def __init__(self) -> None:
        super().__init__(Proveedor)
