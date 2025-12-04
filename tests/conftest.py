import os
import sys
import pytest
from fastapi.testclient import TestClient

# Forzar base de datos en memoria antes de importar la app
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.database import Base, engine, SessionLocal, get_db  # noqa: E402
from app.models import InventarioPieza, Proveedor  # noqa: E402


@pytest.fixture()
def session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = SessionLocal()
    proveedores = [
        Proveedor(id_proveedor=i, nombre=f"Prov{i}", cantidad=500 + i * 50, tiempo=4 + i)
        for i in range(1, 7)
    ]
    db_session.add_all(proveedores)
    piezas = [
        InventarioPieza(id_pieza=f"P{i}", cantidad=0, id_proveedor=i)
        for i in range(1, 7)
    ]
    db_session.add_all(piezas)
    db_session.commit()
    yield db_session
    db_session.close()


@pytest.fixture()
def app(session):
    app = create_app("testing")

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)
