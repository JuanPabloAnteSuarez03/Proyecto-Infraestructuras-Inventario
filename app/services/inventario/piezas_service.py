from typing import Any
from sqlalchemy.orm import Session
from app.repositories import InventarioPiezasRepository
from app.models import InventarioPieza


class InventarioPiezasService:
    def __init__(self, session: Session, repository: InventarioPiezasRepository | None = None) -> None:
        self.session = session
        self.repository = repository or InventarioPiezasRepository(session)

    def list(self) -> list[InventarioPieza]:
        return self.repository.get_all()

    def reset_all(self) -> int:
        updated = self.session.query(InventarioPieza).update({"cantidad": 0})
        self.session.commit()
        return updated

    def retrieve(self, pieza_id: str) -> InventarioPieza | None:
        return self.repository.get_by_id(pieza_id)

    def create(self, payload: dict[str, Any]) -> InventarioPieza:
        return self.repository.create(**payload)

    def delete(self, pieza_id: str) -> bool:
        return self.repository.delete(pieza_id)

    def update(self, pieza_id: str, payload: dict[str, Any]) -> InventarioPieza | None:
        return self.repository.update(pieza_id, **payload)
