from .inventario_productos_repository import InventarioProductosRepository
from .inventario_piezas_repository import InventarioPiezasRepository
from .proveedores_repository import ProveedoresRepository
from .movimientos_repository import MovimientosRepository
from .solicitudes_repository import SolicitudPiezaRepository
from .ordenes_repository import OrdenFabricacionRepository

__all__ = [
    "InventarioProductosRepository",
    "InventarioPiezasRepository",
    "ProveedoresRepository",
    "MovimientosRepository",
    "SolicitudPiezaRepository",
    "OrdenFabricacionRepository",
]
