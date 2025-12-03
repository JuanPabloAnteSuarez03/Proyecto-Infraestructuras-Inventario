from typing import Any
from ..repositories import SolicitudPiezaRepository
from ..models import SolicitudPieza


class SolicitudesPiezaService:
    def __init__(self, repository: SolicitudPiezaRepository | None = None) -> None:
        self.repository = repository or SolicitudPiezaRepository()

    def list(self) -> list[SolicitudPieza]:
        return self.repository.get_all()

    def retrieve(self, solicitud_id: int) -> SolicitudPieza | None:
        return self.repository.get_by_id(solicitud_id)

    def create(self, payload: dict[str, Any]) -> SolicitudPieza:
        return self.repository.create(**payload)

    def update(self, solicitud_id: int, payload: dict[str, Any]) -> SolicitudPieza | None:
        return self.repository.update(solicitud_id, **payload)
