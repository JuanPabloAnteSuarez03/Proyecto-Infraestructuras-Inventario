from typing import Any
from sqlalchemy.orm import Session
from ..repositories import SolicitudPiezaRepository
from ..models import SolicitudPieza


class SolicitudesPiezaService:
    def __init__(self, session: Session, repository: SolicitudPiezaRepository | None = None) -> None:
        self.session = session
        self.repository = repository or SolicitudPiezaRepository(session)

    def list(self) -> list[SolicitudPieza]:
        return self.repository.get_all()

    def retrieve(self, solicitud_id: int) -> SolicitudPieza | None:
        return self.repository.get_by_id(solicitud_id)

    def create(self, payload: dict[str, Any]) -> SolicitudPieza:
        return self.repository.create(**payload)

    def update(self, solicitud_id: int, payload: dict[str, Any]) -> SolicitudPieza | None:
        return self.repository.update(solicitud_id, **payload)
