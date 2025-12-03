from __future__ import annotations
from dataclasses import dataclass
from ..extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), server_onupdate=db.func.now()
    )


@dataclass
class InventarioProducto(TimestampMixin, db.Model):
    __tablename__ = "inventario_productos"

    id_producto: str = db.Column(db.String(16), primary_key=True)
    estado: str = db.Column(db.String(32), primary_key=True)
    cantidad: int = db.Column(db.Integer, nullable=False)


@dataclass
class Proveedor(TimestampMixin, db.Model):
    __tablename__ = "proveedores"

    id_proveedor: int = db.Column(db.Integer, primary_key=True)
    nombre: str = db.Column(db.String(128), nullable=False)
    cantidad: int = db.Column(db.Integer, nullable=False)
    tiempo: int = db.Column(db.Integer, nullable=False)

    piezas = db.relationship("InventarioPieza", back_populates="proveedor", lazy="selectin")


@dataclass
class InventarioPieza(TimestampMixin, db.Model):
    __tablename__ = "inventario_piezas"

    id_pieza: str = db.Column(db.String(16), primary_key=True)
    cantidad: int = db.Column(db.Integer, nullable=False)
    id_proveedor: int = db.Column(
        db.Integer, db.ForeignKey("proveedores.id_proveedor"), nullable=False
    )

    proveedor = db.relationship("Proveedor", back_populates="piezas")


@dataclass
class Movimiento(TimestampMixin, db.Model):
    __tablename__ = "movimientos"

    id_movimiento: int = db.Column(db.Integer, primary_key=True)
    id_objeto: int = db.Column(db.Integer, nullable=False)
    tipo_objeto: str = db.Column(db.String(64), nullable=False)
    cantidad: int = db.Column(db.Integer, nullable=False)
    direccion: str = db.Column(db.String(32), nullable=False)


@dataclass
class SolicitudPieza(TimestampMixin, db.Model):
    __tablename__ = "solicitudes_piezas"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pieza: str = db.Column(db.String(16), nullable=False)
    cantidad: int = db.Column(db.Integer, nullable=False)
    estado: str = db.Column(db.String(32), nullable=False, default="pendiente")
    tiempo_estimado: int = db.Column(db.Integer, nullable=False, default=0)


@dataclass
class OrdenFabricacion(TimestampMixin, db.Model):
    __tablename__ = "ordenes_fabricacion"

    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_producto: str = db.Column(db.String(16), nullable=False)
    cantidad: int = db.Column(db.Integer, nullable=False)
    estado: str = db.Column(db.String(32), nullable=False, default="pendiente")
    tiempo_estimado: int = db.Column(db.Integer, nullable=False, default=0)
    detalle: dict | None = db.Column(db.JSON, nullable=True)
