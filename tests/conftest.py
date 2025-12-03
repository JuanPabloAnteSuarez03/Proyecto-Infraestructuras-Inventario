import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models import InventarioPieza, Proveedor


@pytest.fixture()
def app():
    app = create_app("testing")
    # El contexto de Flask ya está empujado en create_app; usamos db directamente.
    db.create_all()
    proveedores = [
        Proveedor(id_proveedor=i, nombre=f"Prov{i}", cantidad=500 + i * 50, tiempo=4 + i)
        for i in range(1, 7)
    ]
    db.session.add_all(proveedores)
    piezas = [
        InventarioPieza(id_pieza=f"P{i}", cantidad=0, id_proveedor=i)
        for i in range(1, 7)
    ]
    db.session.add_all(piezas)
    db.session.commit()
    yield app
    db.session.remove()
    db.drop_all()


@pytest.fixture()
def client(app):
    return TestClient(app)
