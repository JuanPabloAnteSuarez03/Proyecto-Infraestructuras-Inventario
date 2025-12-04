from __future__ import annotations
from typing import Any, Type, TypeVar
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")


class BaseRepository:
    def __init__(self, model: Type[ModelType], session: Session):
        self.model = model
        self.session = session

    def get_all(self) -> list[ModelType]:
        return self.session.query(self.model).all()

    def get_by_id(self, record_id: Any) -> ModelType | None:
        return self.session.get(self.model, record_id)

    def create(self, **kwargs) -> ModelType:
        record = self.model(**kwargs)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def delete(self, record_id: Any) -> bool:
        record = self.get_by_id(record_id)
        if not record:
            return False
        self.session.delete(record)
        self.session.commit()
        return True

    def bulk_insert(self, payload: list[dict]) -> None:
        self.session.bulk_insert_mappings(self.model, payload)
        self.session.commit()

    def update(self, record_id: Any, **kwargs) -> ModelType | None:
        record = self.get_by_id(record_id)
        if not record:
            return None
        for key, value in kwargs.items():
            setattr(record, key, value)
        self.session.commit()
        self.session.refresh(record)
        return record
