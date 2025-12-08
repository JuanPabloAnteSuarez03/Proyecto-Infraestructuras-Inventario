from fastapi import FastAPI
from .api import (
    inventario_productos_router,
    inventario_piezas_router,
    proveedores_router,
    movimientos_router,
    fabricacion_router,
    sales_integration_router,
)


def register_routes(app: FastAPI) -> None:
    # API V1 para integración con sistema de ventas
    app.include_router(sales_integration_router)

    # APIs internas
    app.include_router(inventario_productos_router)
    app.include_router(inventario_piezas_router)
    app.include_router(proveedores_router)
    app.include_router(movimientos_router)
    app.include_router(fabricacion_router)
