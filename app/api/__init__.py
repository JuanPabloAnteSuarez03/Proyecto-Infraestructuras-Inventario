from .inventario_productos_controller import router as inventario_productos_router
from .inventario_piezas_controller import router as inventario_piezas_router
from .proveedores_controller import router as proveedores_router
from .movimientos_controller import router as movimientos_router
from .fabricacion_controller import router as fabricacion_router
from .sales_integration_controller import router as sales_integration_router

__all__ = [
    "inventario_productos_router",
    "inventario_piezas_router",
    "proveedores_router",
    "movimientos_router",
    "fabricacion_router",
    "sales_integration_router",
]
