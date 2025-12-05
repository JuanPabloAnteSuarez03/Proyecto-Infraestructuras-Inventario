"""
Modelos de respuesta de la API.

Este módulo define los esquemas Pydantic para las respuestas de la API,
proporcionando validación automática y documentación OpenAPI.
"""

from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


# === Respuestas de Inventario ===

class ReservaResponse(BaseModel):
    """Respuesta de una operación de reserva de productos."""

    id_producto: str = Field(..., description="Código del producto (S1, S2)")
    cantidad_solicitada: int = Field(..., description="Cantidad solicitada para reserva")
    cantidad_confirmada: int = Field(..., description="Cantidad efectivamente reservada")
    cantidad_pendiente: int = Field(..., description="Cantidad pendiente (si hubo fabricación)")
    cantidad_disponible: int = Field(..., description="Cantidad disponible después de la reserva")
    tiempo_estimado: int = Field(..., description="Tiempo estimado en minutos para completar")
    estado_ingreso: str = Field(..., description="Estado donde se ingresará el producto")
    reservado: bool = Field(..., description="Si la reserva fue exitosa")
    fabricado: bool = Field(default=False, description="Si se activó fabricación")

    class Config:
        json_schema_extra = {
            "example": {
                "id_producto": "S1",
                "cantidad_solicitada": 100,
                "cantidad_confirmada": 100,
                "cantidad_pendiente": 0,
                "cantidad_disponible": 500,
                "tiempo_estimado": 0,
                "estado_ingreso": "Reservado",
                "reservado": True,
                "fabricado": False,
            }
        }


class DespachoResponse(BaseModel):
    """Respuesta de una operación de despacho de productos."""

    id_producto: str = Field(..., description="Código del producto")
    cantidad_solicitada: int = Field(..., description="Cantidad solicitada para despacho")
    cantidad_confirmada: int = Field(..., description="Cantidad efectivamente despachada")
    cantidad_pendiente: int = Field(..., description="Cantidad pendiente")
    tiempo_estimado: int = Field(..., description="Tiempo estimado en minutos")
    estado_ingreso: str = Field(..., description="Estado de origen del despacho")
    despachado: bool = Field(..., description="Si el despacho fue exitoso")

    class Config:
        json_schema_extra = {
            "example": {
                "id_producto": "S1",
                "cantidad_solicitada": 50,
                "cantidad_confirmada": 50,
                "cantidad_pendiente": 0,
                "tiempo_estimado": 0,
                "estado_ingreso": "A Despacho",
                "despachado": True,
            }
        }


# === Respuestas de Fabricación ===

class MaterialRequired(BaseModel):
    """Material requerido para fabricación."""

    id_pieza: str = Field(..., description="Código de la pieza")
    cantidad_requerida: int = Field(..., description="Cantidad total requerida")
    cantidad_disponible: int = Field(..., description="Cantidad disponible en inventario")
    cantidad_faltante: int = Field(default=0, description="Cantidad faltante")


class PlanFabricacionResponse(BaseModel):
    """Respuesta con el plan de fabricación."""

    id_producto: str = Field(..., description="Código del producto a fabricar")
    cantidad_solicitada: int = Field(..., description="Cantidad solicitada")
    materiales: list[MaterialRequired] = Field(..., description="Lista de materiales requeridos")
    tiempo_estimado: int = Field(..., description="Tiempo estimado de fabricación en minutos")
    plano_id: str | None = Field(None, description="ID del plano en sistema externo")

    class Config:
        json_schema_extra = {
            "example": {
                "id_producto": "S1",
                "cantidad_solicitada": 100,
                "materiales": [
                    {
                        "id_pieza": "P1",
                        "cantidad_requerida": 100,
                        "cantidad_disponible": 500,
                        "cantidad_faltante": 0,
                    }
                ],
                "tiempo_estimado": 30,
                "plano_id": "plano-S1",
            }
        }


class ProduccionResponse(BaseModel):
    """Respuesta de una operación de producción."""

    id_producto: str = Field(..., description="Código del producto fabricado")
    cantidad_solicitada: int = Field(..., description="Cantidad solicitada")
    cantidad_producida: int = Field(..., description="Cantidad efectivamente producida")
    materiales_consumidos: list[dict] = Field(default_factory=list, description="Materiales consumidos")
    tiempo_total: int = Field(..., description="Tiempo total de producción en minutos")

    class Config:
        json_schema_extra = {
            "example": {
                "id_producto": "S1",
                "cantidad_solicitada": 100,
                "cantidad_producida": 100,
                "materiales_consumidos": [],
                "tiempo_total": 30,
            }
        }


class CalculoPiezasItem(BaseModel):
    """Item de cálculo de piezas requeridas."""

    codigo: str = Field(..., description="Código de la pieza")
    cantidad_por_unidad: int = Field(..., description="Cantidad requerida por unidad de producto")
    cantidad_total: int = Field(..., description="Cantidad total requerida")


class CalculoPiezasResponse(BaseModel):
    """Respuesta del cálculo de piezas necesarias."""

    codigo: str = Field(..., description="Código del producto")
    cantidad_solicitada: int = Field(..., description="Cantidad de productos a fabricar")
    piezas: list[CalculoPiezasItem] = Field(..., description="Lista de piezas necesarias")

    class Config:
        json_schema_extra = {
            "example": {
                "codigo": "S1",
                "cantidad_solicitada": 10,
                "piezas": [
                    {"codigo": "P1", "cantidad_por_unidad": 1, "cantidad_total": 10},
                    {"codigo": "P2", "cantidad_por_unidad": 1, "cantidad_total": 10},
                ],
            }
        }


# === Respuestas de Proveedores ===

class SolicitudPiezaResponse(BaseModel):
    """Respuesta de una solicitud de piezas a proveedor."""

    id_pieza: str = Field(..., description="Código de la pieza solicitada")
    cantidad_solicitada: int = Field(..., description="Cantidad solicitada")
    cantidad_recibida: int = Field(..., description="Cantidad recibida del proveedor")
    tiempo_entrega: int = Field(..., description="Tiempo de entrega en minutos")
    proveedor_id: int | None = Field(None, description="ID del proveedor que suministró")

    class Config:
        json_schema_extra = {
            "example": {
                "id_pieza": "P1",
                "cantidad_solicitada": 100,
                "cantidad_recibida": 100,
                "tiempo_entrega": 10,
                "proveedor_id": 1,
            }
        }


# === Respuestas Genéricas ===

class MessageResponse(BaseModel):
    """Respuesta genérica con un mensaje."""

    message: str = Field(..., description="Mensaje de respuesta")
    success: bool = Field(default=True, description="Si la operación fue exitosa")

    class Config:
        json_schema_extra = {
            "example": {"message": "Operación completada exitosamente", "success": True}
        }


class ErrorResponse(BaseModel):
    """Respuesta de error estandarizada."""

    error: str = Field(..., description="Tipo de error")
    detail: str = Field(..., description="Detalle del error")
    code: str = Field(..., description="Código de error")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp del error")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "InsufficientStockError",
                "detail": "Stock insuficiente para S1: requiere 100, disponible 50",
                "code": "INSUFFICIENT_STOCK",
                "timestamp": "2024-12-04T22:00:00Z",
            }
        }