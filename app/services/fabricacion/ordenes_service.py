from typing import Any
from sqlalchemy.orm import Session
from app.repositories import OrdenFabricacionRepository
from app.models import OrdenFabricacion


class OrdenesFabricacionService:
    def __init__(self, session: Session, repository: OrdenFabricacionRepository | None = None) -> None:
        self.session = session
        self.repository = repository or OrdenFabricacionRepository(session)

    def list(self) -> list[OrdenFabricacion]:
        return self.repository.get_all()

    def delete_all(self) -> int:
        deleted = self.session.query(OrdenFabricacion).delete()
        self.session.commit()
        return deleted

    def retrieve(self, orden_id: int) -> OrdenFabricacion | None:
        return self.repository.get_by_id(orden_id)

    def create(self, payload: dict[str, Any]) -> OrdenFabricacion:
        return self.repository.create(**payload)

    def update(self, orden_id: int, payload: dict[str, Any]) -> OrdenFabricacion | None:
        return self.repository.update(orden_id, **payload)
