from fastapi import FastAPI
from .controllers import (
    inventario_productos_router,
    inventario_piezas_router,
    proveedores_router,
    movimientos_router,
    fabricacion_router,
)


def register_routes(app: FastAPI) -> None:
    app.include_router(inventario_productos_router)
    app.include_router(inventario_piezas_router)
    app.include_router(proveedores_router)
    app.include_router(movimientos_router)
    app.include_router(fabricacion_router)
