from __future__ import annotations
import json
from pathlib import Path
from ..extensions import db
from ..models import InventarioProducto, InventarioPieza, Proveedor, Movimiento

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"


def load_seed_data() -> None:
    """Populate the database with data stored in JSON files."""
    mapping = [
        ("proveedores.json", Proveedor),
        ("inventario_productos.json", InventarioProducto),
        ("inventario_piezas.json", InventarioPieza),
        ("movimientos.json", Movimiento),
    ]

    for filename, model in mapping:
        file_path = DATA_DIR / filename
        if not file_path.exists():
            continue
        with file_path.open("r", encoding="utf-8") as handler:
            payload = json.load(handler)
            db.session.bulk_insert_mappings(model, payload)
    db.session.commit()
