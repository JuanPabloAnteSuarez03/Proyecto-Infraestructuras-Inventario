from __future__ import annotations
from typing import Any, Type
from ..extensions import db


class BaseRepository:
    def __init__(self, model: Type[db.Model]):
        self.model = model

    def get_all(self) -> list[db.Model]:
        return self.model.query.all()

    def get_by_id(self, record_id: Any) -> db.Model | None:
        return db.session.get(self.model, record_id)

    def create(self, **kwargs) -> db.Model:
        record = self.model(**kwargs)
        db.session.add(record)
        db.session.commit()
        return record

    def delete(self, record_id: Any) -> bool:
        record = self.get_by_id(record_id)
        if not record:
            return False
        db.session.delete(record)
        db.session.commit()
        return True

    def bulk_insert(self, payload: list[dict]) -> None:
        db.session.bulk_insert_mappings(self.model, payload)
        db.session.commit()

    def update(self, record_id: Any, **kwargs) -> db.Model | None:
        record = self.get_by_id(record_id)
        if not record:
            return None
        for key, value in kwargs.items():
            setattr(record, key, value)
        db.session.commit()
        return record
