from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column, relationship
from ..database import Base


@declarative_mixin
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class InventarioProducto(TimestampMixin, Base):
    __tablename__ = "inventario_productos"

    id_producto: Mapped[str] = mapped_column(String(16), primary_key=True)
    estado: Mapped[str] = mapped_column(String(32), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)


class Proveedor(TimestampMixin, Base):
    __tablename__ = "proveedores"

    id_proveedor: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    tiempo: Mapped[int] = mapped_column(Integer, nullable=False)

    piezas: Mapped[list["InventarioPieza"]] = relationship(
        "InventarioPieza", back_populates="proveedor", lazy="selectin"
    )


class InventarioPieza(TimestampMixin, Base):
    __tablename__ = "inventario_piezas"

    id_pieza: Mapped[str] = mapped_column(String(16), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    id_proveedor: Mapped[int] = mapped_column(
        Integer, ForeignKey("proveedores.id_proveedor"), nullable=False
    )

    proveedor: Mapped[Proveedor] = relationship("Proveedor", back_populates="piezas")


class Movimiento(TimestampMixin, Base):
    __tablename__ = "movimientos"

    id_movimiento: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_objeto: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_objeto: Mapped[str] = mapped_column(String(64), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    direccion: Mapped[str] = mapped_column(String(32), nullable=False)


class SolicitudPieza(TimestampMixin, Base):
    __tablename__ = "solicitudes_piezas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_pieza: Mapped[str] = mapped_column(String(16), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(32), nullable=False, default="pendiente")
    tiempo_estimado: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OrdenFabricacion(TimestampMixin, Base):
    __tablename__ = "ordenes_fabricacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_producto: Mapped[str] = mapped_column(String(16), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(32), nullable=False, default="pendiente")
    tiempo_estimado: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detalle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
