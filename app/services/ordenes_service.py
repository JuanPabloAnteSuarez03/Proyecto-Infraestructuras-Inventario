from typing import Any
from ..repositories import OrdenFabricacionRepository
from ..models import OrdenFabricacion


class OrdenesFabricacionService:
    def __init__(self, repository: OrdenFabricacionRepository | None = None) -> None:
        self.repository = repository or OrdenFabricacionRepository()

    def list(self) -> list[OrdenFabricacion]:
        return self.repository.get_all()

    def retrieve(self, orden_id: int) -> OrdenFabricacion | None:
        return self.repository.get_by_id(orden_id)

    def create(self, payload: dict[str, Any]) -> OrdenFabricacion:
        return self.repository.create(**payload)

    def update(self, orden_id: int, payload: dict[str, Any]) -> OrdenFabricacion | None:
        return self.repository.update(orden_id, **payload)
