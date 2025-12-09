from __future__ import annotations
from pydantic import BaseModel, field_validator, model_validator
from typing import Any


class ProductoCreate(BaseModel):
    id_producto: str
    estado: str
    cantidad: int


class ProductoUpdate(BaseModel):
    cantidad: int


class IngresoProducto(BaseModel):
    model_config = {"extra": "allow"}  # Permitir campos extras

    id_producto: str | None = None
    cantidad: int
    estado: str | None = "Disponible"

    @model_validator(mode='before')
    @classmethod
    def normalize_producto_id(cls, data: Any) -> Any:
        """Acepta tanto 'codigo' como 'id_producto' para compatibilidad con fábrica externa"""
        # Mapeo de códigos externos a códigos internos
        codigo_mapping = {"1": "S1", "S2": "S2"}

        if isinstance(data, dict):
            # Si viene 'codigo' pero no 'id_producto', copiar el valor y eliminar 'codigo'
            if data.get('codigo') and not data.get('id_producto'):
                codigo_externo = str(data.pop('codigo'))  # pop elimina 'codigo' del dict
                # Convertir código externo a código interno si es necesario
                data['id_producto'] = codigo_mapping.get(codigo_externo, codigo_externo)
            elif data.get('codigo') and data.get('id_producto'):
                # Si vienen ambos, eliminar 'codigo' para evitar conflictos
                data.pop('codigo', None)
            # Validar que al menos uno exista
            if not data.get('id_producto'):
                raise ValueError("Se requiere 'id_producto' o 'codigo'")
        return data


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

class PedidoOnline(BaseModel):
    id_producto: str
    cantidad: int


class PedidoLocal(BaseModel):
    id_producto: str
    cantidad: int


class RetiroLocal(BaseModel):
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


class EntregaOrden(BaseModel):
    cantidad: int
