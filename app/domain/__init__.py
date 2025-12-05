from .inventario import PRODUCT_CODES, PRODUCT_STATES, normalize_producto_codigo, normalize_estado
from .exceptions import (
    # Base exceptions
    DomainException,
    # Inventory exceptions
    InventoryException,
    InsufficientStockError,
    InvalidProductError,
    InvalidStateError,
    ProductNotFoundError,
    # Manufacturing exceptions
    ManufacturingException,
    ManufacturingFailureError,
    InvalidManufacturingPlanError,
    InsufficientPartsError,
    # Supplier exceptions
    SupplierException,
    SupplierNotFoundError,
    SupplierRequestFailedError,
    # Validation exceptions
    ValidationError,
    InvalidQuantityError,
)

__all__ = [
    # Constants and functions
    "PRODUCT_CODES",
    "PRODUCT_STATES",
    "normalize_producto_codigo",
    "normalize_estado",
    # Exceptions
    "DomainException",
    "InventoryException",
    "InsufficientStockError",
    "InvalidProductError",
    "InvalidStateError",
    "ProductNotFoundError",
    "ManufacturingException",
    "ManufacturingFailureError",
    "InvalidManufacturingPlanError",
    "InsufficientPartsError",
    "SupplierException",
    "SupplierNotFoundError",
    "SupplierRequestFailedError",
    "ValidationError",
    "InvalidQuantityError",
]
