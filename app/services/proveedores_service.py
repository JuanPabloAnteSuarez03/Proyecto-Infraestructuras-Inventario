from typing import Any
from ..repositories import ProveedoresRepository, InventarioPiezasRepository
from ..models import Proveedor
from ..extensions import db


class ProveedoresService:
    def __init__(self, repository: ProveedoresRepository | None = None, piezas_repository: InventarioPiezasRepository | None = None) -> None:
        self.repository = repository or ProveedoresRepository()
        self.piezas_repository = piezas_repository or InventarioPiezasRepository()

    def list(self) -> list[Proveedor]:
        return self.repository.get_all()

    def retrieve(self, proveedor_id: int) -> Proveedor | None:
        return self.repository.get_by_id(proveedor_id)

    def create(self, payload: dict[str, Any]) -> Proveedor:
        return self.repository.create(**payload)

    def delete(self, proveedor_id: int) -> bool:
        return self.repository.delete(proveedor_id)

    def update(self, proveedor_id: int, payload: dict[str, Any]) -> Proveedor | None:
        return self.repository.update(proveedor_id, **payload)

    def solicitar_piezas(self, pieza_id: str, cantidad: int) -> dict[str, Any]:
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        pieza = self.piezas_repository.get_by_id(pieza_id)
        if not pieza:
            raise ValueError("La pieza solicitada no existe")
        proveedor = pieza.proveedor or self.retrieve(pieza.id_proveedor)
        tiempo = proveedor.tiempo if proveedor else 0
        pieza.cantidad += cantidad
        db.session.commit()
        return {
            "id_pieza": pieza_id,
            "id_proveedor": pieza.id_proveedor,
            "cantidad_recibida": cantidad,
            "tiempo_entrega": tiempo,
            "cantidad_total": pieza.cantidad,
        }
