from __future__ import annotations
from pydantic import BaseModel


class ProductoCreate(BaseModel):
    id_producto: str
    estado: str
    cantidad: int


class ProductoUpdate(BaseModel):
    cantidad: int


class IngresoProducto(BaseModel):
    id_producto: str
    cantidad: int
    estado: str | None = "Disponible"


class Transferencia(BaseModel):
    id_producto: str
    estado_origen: str
    estado_destino: str
    cantidad: int


class Reserva(BaseModel):
    id_producto: str
    cantidad: int


class Despacho(BaseModel):
    id_producto: str
    cantidad: int


class PiezaCreate(BaseModel):
    id_pieza: str
    cantidad: int
    id_proveedor: int


class PiezaUpdate(BaseModel):
    cantidad: int | None = None
    id_proveedor: int | None = None


class ProveedorCreate(BaseModel):
    id_proveedor: int
    nombre: str
    cantidad: int
    tiempo: int


class ProveedorUpdate(BaseModel):
    nombre: str | None = None
    cantidad: int | None = None
    tiempo: int | None = None


class SolicitudPiezas(BaseModel):
    id_pieza: str
    cantidad: int


class MovimientoCreate(BaseModel):
    id_movimiento: int
    id_objeto: int
    tipo_objeto: str
    cantidad: int
    direccion: str


class MovimientoUpdate(BaseModel):
    id_objeto: int | None = None
    tipo_objeto: str | None = None
    cantidad: int | None = None
    direccion: str | None = None


class SolicitudFabricacion(BaseModel):
    id_producto: str
    cantidad: int


class CalculoPiezas(BaseModel):
    codigo: str
    cantidad: int


class SolicitudPiezaAsync(BaseModel):
    id_pieza: str
    cantidad: int


class OrdenFabricacionAsync(BaseModel):
    id_producto: str
    cantidad: int
