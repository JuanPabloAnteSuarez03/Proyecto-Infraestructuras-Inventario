# 🧪 Guía de Testing

## Introducción

Esta guía cubre cómo testear el sistema de inventario, incluyendo pruebas unitarias, de integración y de workers asíncronos.

## Configuración de Testing

### Instalación de Dependencias

```bash
#  Instalar dependencias de desarrollo
pip install -r requirements-dev.txt
```

**requirements-dev.txt:**
```
pytest==7.4.3
pytest-cov==4.1.0
pytest-asyncio==0.21.1
```

### Configuración de Test Database

Los tests usan SQLite en memoria por defecto para aislar las pruebas.

**Archivo:** `tests/conftest.py`

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base

@pytest.fixture(scope="function")
def test_db_session():
    """Crear sesión de BD en memoria para cada test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)
```

## Ejecutar Tests

### Todos los Tests

```bash
# Dentro del contenedor
docker compose exec api pytest

# Localmente (si tienes Python configurado)
pytest
```

### Tests con Verbosity

```bash
pytest -v
# Muestra cada test individualmente
```

### Tests Específicos

```bash
# Un archivo específico
pytest tests/test_productos.py

# Una clase específica
pytest tests/test_productos.py::TestProductosService

# Un test específico
pytest tests/test_productos.py::test_incrementar_stock
```

### Coverage

```bash
# Ver cobertura
pytest --cov=app tests/

# Generar reporte HTML
pytest --cov=app --cov-report=html tests/
# Abre htmlcov/index.html
```

## Tests de Servicios

### Ejemplo: Test de ProductosService

**Archivo:** `tests/test_productos_service.py`

```python
import pytest
from app.services.inventario.productos_service import InventarioProductosService
from app.repositories.productos_repository import InventarioProductosRepository

def test_incrementar_stock(test_db_session):
    """Test de incremento de stock."""
    # Arrange
    repo = InventarioProductosRepository(test_db_session)
    service = InventarioProductosService(test_db_session, repository=repo)
    
    # Crear producto inicial
    repo.create({"id_producto": "S1", "estado": "Disponible", "cantidad": 100})
    
    # Act
    service.incrementar_stock("S1", 50, "Disponible")
    
    # Assert
    producto = repo.get_by_codigo_estado("S1", "Disponible")
    assert producto.cantidad == 150

def test_transferir_stock(test_db_session):
    """Test de transferencia entre estados."""
    # Arrange
    repo = InventarioProductosRepository(test_db_session)
    service = InventarioProductosService(test_db_session, repository=repo)
    
    repo.create({"id_producto": "S1", "estado": "Disponible", "cantidad": 100})
    repo.create({"id_producto": "S1", "estado": "Reservado", "cantidad": 0})
    
    # Act
    service.transferir_stock("S1", "Disponible", "Reservado", 30)
    
    # Assert
    disponible = repo.get_by_codigo_estado("S1", "Disponible")
    reservado = repo.get_by_codigo_estado("S1", "Reservado")
    assert disponible.cantidad == 70
    assert reservado.cantidad == 30

def test_transferir_stock_insuficiente(test_db_session):
    """Test de transferencia con stock insuficiente."""
    # Arrange
    repo = InventarioProductosRepository(test_db_session)
    service = InventarioProductosService(test_db_session, repository=repo)
    
    repo.create({"id_producto": "S1", "estado": "Disponible", "cantidad": 10})
    repo.create({"id_producto": "S1", "estado": "Reservado", "cantidad": 0})
    
    # Act & Assert
    with pytest.raises(ValueError, match="Stock insuficiente"):
        service.transferir_stock("S1", "Disponible", "Reservado", 50)
```

## Tests de Endpoints (FastAPI)

### Usando TestClient

**Archivo:** `tests/test_api_productos.py`

```python
from fastapi.testclient import TestClient
from app import create_app

@pytest.fixture
def client():
    """Cliente de test para FastAPI."""
    app = create_app()
    return TestClient(app)

def test_listar_productos(client):
    """Test GET /api/productos."""
    response = client.get("/api/productos")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_crear_producto(client):
    """Test POST /api/productos."""
    payload = {
        "id_producto": "S1",
        "estado": "Disponible",
        "cantidad": 100
    }
    response = client.post("/api/productos", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id_producto"] == "S1"
    assert data["cantidad"] == 100

def test_transferencia(client):
    """Test POST /api/productos/transferencias."""
    payload = {
        "id_producto": "S1",
        "estado_origen": "Disponible",
        "estado_destino": "Reservado",
        "cantidad": 30
    }
    response = client.post("/api/productos/transferencias", json=payload)
    assert response.status_code == 200
```

## Tests de Workers (RQ)

### Mockear Cola

**Archivo:** `tests/test_workers.py`

```python
from unittest.mock import Mock, patch
from app.tasks import procesar_solicitud_pieza

def test_procesar_solicitud_pieza(test_db_session):
    """Test del worker de solicitud de pieza."""
    # Arrange: Crear datos iniciales
    from app.services.proveedores.solicitudes_service import SolicitudesPiezaService
    from app.services.inventario.piezas_service import InventarioPiezasService
    from app.services.proveedores.proveedores_service import ProveedoresService
    
    # Crear proveedor
    proveedores_service = ProveedoresService(test_db_session)
    proveedor = proveedores_service.create({
        "id_proveedor": 1,
        "nombre": "Prov1",
        "cantidad": 1000,
        "tiempo": 5
    })
    
    # Crear pieza
    piezas_service = Invent arioPiezasService(test_db_session)
    pieza = piezas_service.create({
        "id_pieza": 1,
        "nombre": "Pieza 1",
        "cantidad": 50,
        "id_proveedor": 1
    })
    
    # Crear solicitud
    solicitudes_service = SolicitudesPiezaService(test_db_session)
    solicitud = solicitudes_service.create({
        "id_pieza": 1,
        "cantidad": 100,
        "estado": "pendiente"
    })
    
    # Act: Ejecutar worker
    with patch('time.sleep'):  # Mockear sleep para que sea instantáneo
        procesar_solicitud_pieza(solicitud.id)
    
    # Assert
    solicitud_actualizada = solicitudes_service.retrieve(solicitud.id)
    assert solicitud_actualizada.estado == "completada"
    
    pieza_actualizada = piezas_service.retrieve(1)
    assert pieza_actualizada.cantidad == 150  # 50 + 100
```

## Tests de Integración

### Test de Flujo Completo

**Archivo:** `tests/test_integration.py`

```python
def test_flujo_solicitud_asincrona(client, test_db_session):
    """Test del flujo completo de solicitud asíncrona."""
    # 1. Setup: Crear proveedor y pieza
    # ... (crear datos iniciales)
    
    # 2. Solicitar pieza asíncronamente
    response = client.post("/api/proveedores/solicitudes_async", json={
        "id_pieza": 1,
        "cantidad": 100
    })
    assert response.status_code == 202
    data = response.json()
    solicitud_id = data["id"]
    assert data["estado"] == "pendiente"
    
    # 3. Simular procesamiento del worker
    with patch('time.sleep'):
        procesar_solicitud_pieza(solicitud_id)
    
    # 4. Verificar que solicitud está completada
    response = client.get(f"/api/proveedores/solicitudes_async/{solicitud_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "completada"
    
    # 5. Verificar que inventario se actualizó
    response = client.get("/api/piezas/1")
    data = response.json()
    assert data["cantidad"] == 150  # Cantidad inicial + 100
```

## Comandos CLI de Testing

### Ejecutar Tests con Docker

```bash
# Ejecutar todos los tests
docker compose exec api pytest

# Con verbosity
docker compose exec api pytest -v

# Con coverage
docker compose exec api pytest --cov=app tests/

# Test específico
docker compose exec api pytest tests/test_productos.py -v

# Filtrar por nombre
docker compose exec api pytest -k "transferir" -v
```

### Testing Local (sin Docker)

```bash
# Setup
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Ejecutar
pytest
```

## Estructura de Tests

```
tests/
├── conftest.py                    # Fixtures compartidos
├── test_productos_service.py      # Tests de ProductosService
├── test_piezas_service.py         # Tests de PiezasService
├── test_proveedores_service.py    # Tests de ProveedoresService
├── test_ordenes_service.py        # Tests de OrdenesService
├── test_workers.py                # Tests de workers RQ
├── test_api_productos.py          # Tests de endpoints /api/productos
├── test_api_proveedores.py        # Tests de endpoints /api/proveedores
├── test_api_fabricacion.py        # Tests de endpoints /api/fabricacion
└── test_integration.py            # Tests de integración
```

## Mejores Prácticas

### ✅ DO

1. **Usar fixtures para setup**
   ```python
   @pytest.fixture
   def producto_inicial(test_db_session):
       repo = InventarioProductosRepository(test_db_session)
       return repo.create({"id_producto": "S1", "estado": "Disponible", "cantidad": 100})
   ```

2. **Nombrar tests descriptivamente**
   ```python
   def test_transferir_stock_cuando_hay_suficiente_entonces_actualiza_ambos_estados():
       ...
   ```

3. **Seguir patrón AAA (Arrange, Act, Assert)**
   ```python
   def test_ejemplo():
       # Arrange - Preparar datos
       ...
       # Act - Ejecutar acción
       ...
       # Assert - Verificar resultado
       ...
   ```

4. **Mockear dependencias externas**
   ```python
   with patch('app.services.fabricacion.fabricacion_service.httpx.get') as mock_get:
       mock_get.return_value.json.return_value = {"status": "ok"}
       ...
   ```

### ❌ DON'T

1. **No usar base de datos real en tests**
2. **No hacer tests que dependan de orden**
3. **No dejar prints/logs innecesarios**
4. **No testear implementación, testear comportamiento**

## Debugging Tests

### Con pdb

```python
def test_ejemplo():
    import pdb; pdb.set_trace()
    # Debugger se detendrá aquí
    ...
```

### Con pytest -s

```bash
# Mostrar prints
pytest -s tests/test_productos.py
```

### Con verbosity máxima

```bash
pytest -vv tests/
```

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: pytest --cov=app tests/
```

## Próximos Pasos

1. **Escribe tests para tu código nuevo**
2. **Mantén coverage > 80%**
3. **Ejecuta tests antes de hacer commit**
4. **Lee los tests existentes en `tests/` para entender patrones**

---

**Happy Testing!** 🧪
