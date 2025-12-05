from typing import Any
from sqlalchemy.orm import Session
from app.repositories import MovimientosRepository
from app.models import Movimiento


class MovimientosService:
    def __init__(self, session: Session, repository: MovimientosRepository | None = None) -> None:
        self.session = session
        self.repository = repository or MovimientosRepository(session)

    def list(self) -> list[Movimiento]:
        return self.repository.get_all()

    def retrieve(self, movimiento_id: int) -> Movimiento | None:
        return self.repository.get_by_id(movimiento_id)

    def create(self, payload: dict[str, Any]) -> Movimiento:
        return self.repository.create(**payload)

    def delete(self, movimiento_id: int) -> bool:
        return self.repository.delete(movimiento_id)

    def update(self, movimiento_id: int, payload: dict[str, Any]) -> Movimiento | None:
        return self.repository.update(movimiento_id, **payload)
