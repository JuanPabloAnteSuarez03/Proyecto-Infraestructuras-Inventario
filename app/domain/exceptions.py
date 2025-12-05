"""
Excepciones del dominio de inventario y fabricación.

Este módulo define la jerarquía de excepciones específicas del negocio,
permitiendo un manejo de errores más preciso y expresivo.
"""

from __future__ import annotations


# Base Exception
class DomainException(Exception):
    """Excepción base para todos los errores del dominio."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


# Inventory Exceptions
class InventoryException(DomainException):
    """Excepción base para errores relacionados con inventario."""
    pass


class InsufficientStockError(InventoryException):
    """Error cuando no hay suficiente stock disponible."""

    def __init__(
        self,
        producto_id: str,
        required: int,
        available: int,
        estado: str = "Disponible"
    ):
        self.producto_id = producto_id
        self.required = required
        self.available = available
        self.estado = estado

        message = (
            f"Stock insuficiente para {producto_id} en estado {estado}: "
            f"requiere {required}, disponible {available}"
        )
        details = {
            "producto_id": producto_id,
            "cantidad_requerida": required,
            "cantidad_disponible": available,
            "estado": estado,
            "deficit": required - available,
        }
        super().__init__(message, details)


class InvalidProductError(InventoryException):
    """Error cuando el código de producto o estado es inválido."""

    def __init__(self, producto_id: str, reason: str = "Producto no válido"):
        self.producto_id = producto_id
        message = f"Producto inválido '{producto_id}': {reason}"
        details = {"producto_id": producto_id, "reason": reason}
        super().__init__(message, details)


class InvalidStateError(InventoryException):
    """Error cuando el estado del producto es inválido."""

    def __init__(self, estado: str, valid_states: list[str] | None = None):
        self.estado = estado
        self.valid_states = valid_states or []

        message = f"Estado inválido '{estado}'"
        if valid_states:
            message += f". Estados válidos: {', '.join(valid_states)}"

        details = {"estado": estado, "estados_validos": valid_states}
        super().__init__(message, details)


class ProductNotFoundError(InventoryException):
    """Error cuando no se encuentra un producto en inventario."""

    def __init__(self, producto_id: str, estado: str | None = None):
        self.producto_id = producto_id
        self.estado = estado

        message = f"Producto no encontrado: {producto_id}"
        if estado:
            message += f" en estado {estado}"

        details = {"producto_id": producto_id, "estado": estado}
        super().__init__(message, details)


# Manufacturing Exceptions
class ManufacturingException(DomainException):
    """Excepción base para errores de fabricación."""
    pass


class ManufacturingFailureError(ManufacturingException):
    """Error cuando falla el servicio de fabricación externo."""

    def __init__(self, reason: str, response_data: dict | None = None):
        message = f"Error en servicio de fabricación: {reason}"
        details = {"reason": reason, "response": response_data}
        super().__init__(message, details)


class InvalidManufacturingPlanError(ManufacturingException):
    """Error cuando el plan de fabricación es inválido."""

    def __init__(self, producto_id: str, reason: str):
        self.producto_id = producto_id
        message = f"Plan de fabricación inválido para {producto_id}: {reason}"
        details = {"producto_id": producto_id, "reason": reason}
        super().__init__(message, details)


class InsufficientPartsError(ManufacturingException):
    """Error cuando no hay suficientes piezas para fabricar."""

    def __init__(self, pieza_id: str, required: int, available: int):
        self.pieza_id = pieza_id
        self.required = required
        self.available = available

        message = (
            f"Piezas insuficientes: {pieza_id} requiere {required}, "
            f"disponible {available}"
        )
        details = {
            "pieza_id": pieza_id,
            "cantidad_requerida": required,
            "cantidad_disponible": available,
            "deficit": required - available,
        }
        super().__init__(message, details)


# Supplier Exceptions
class SupplierException(DomainException):
    """Excepción base para errores de proveedores."""
    pass


class SupplierNotFoundError(SupplierException):
    """Error cuando no se encuentra un proveedor."""

    def __init__(self, proveedor_id: int):
        self.proveedor_id = proveedor_id
        message = f"Proveedor no encontrado: {proveedor_id}"
        details = {"proveedor_id": proveedor_id}
        super().__init__(message, details)


class SupplierRequestFailedError(SupplierException):
    """Error cuando falla una solicitud a proveedor."""

    def __init__(self, pieza_id: str, cantidad: int, reason: str):
        self.pieza_id = pieza_id
        self.cantidad = cantidad

        message = (
            f"Falló solicitud de {cantidad} unidades de {pieza_id}: {reason}"
        )
        details = {
            "pieza_id": pieza_id,
            "cantidad": cantidad,
            "reason": reason,
        }
        super().__init__(message, details)


# Validation Exceptions
class ValidationError(DomainException):
    """Error de validación de datos de entrada."""

    def __init__(self, field: str, value: any, reason: str):
        self.field = field
        self.value = value

        message = f"Validación fallida en campo '{field}': {reason}"
        details = {"field": field, "value": str(value), "reason": reason}
        super().__init__(message, details)


class InvalidQuantityError(ValidationError):
    """Error cuando la cantidad es inválida."""

    def __init__(self, cantidad: int, min_value: int = 1):
        message = f"Cantidad inválida: {cantidad} (debe ser >= {min_value})"
        super().__init__("cantidad", cantidad, message)
