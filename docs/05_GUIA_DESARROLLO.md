# 🛠️ Guía de Desarrollo

## Introducción

Esta guía te enseñará cómo extender el sistema de inventario agregando nuevas funcionalidades. Aprenderás patrones comunes, mejores prácticas y ejemplos prácticos.

## Requisitos Previos

Antes de empezar, deberías haber leído:
- [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md) - Entender la estructura
- [02_SISTEMA_COLAS.md](02_SISTEMA_COLAS.md) - Comprender RQ
- [03_PARALELISMO_CONCURRENCIA.md](03_PARALELISMO_CONCURRENCIA.md) - Gestión de estado

## Setup de Desarrollo

### 1. Clonar y Configurar

```bash
# Clonar repositorio
git clone <repo_url>
cd Proyecto-Infraestructuras-Inventario

# Copiar variables de entorno
cp .env.example .env

# Levantar servicios
docker compose up --build

# En otra terminal: Crear BD y cargar datos
docker compose exec api python -m app.cli create-db
docker compose exec api python -m app.cli seed-db
```

### 2. Verificar Instalación

```bash
# Probar API
curl http://localhost:5050/health
# Respuesta: {"status": "ok"}

# Probar endpoints
curl http://localhost:5050/api/productos
curl http://localhost:5050/api/piezas
```

### 3. Herramientas Recomendadas

- **IDE:** VS Code, PyCharm
- **Cliente HTTP:** Postman, Insomnia, curl
- **DB Client:** pgAdmin, DBeaver
- **Monitoreo:** Docker Desktop, `docker compose logs`

---

## Patrón 1: Agregar un Nuevo Endpoint Síncrono

### Caso de Uso
Crear endpoint `GET /api/productos/{codigo}/estados` que retorne todos los estados de un producto.

### Paso 1: Definir Schema Pydantic

**Archivo:** `app/schemas/api_models.py`

```python
from pydantic import BaseModel

class EstadosProductoResponse(BaseModel):
    id_producto: str
    estados: list[dict]  # Lista de {"estado": "Disponible", "cantidad": 100}
```

### Paso 2: Agregar Método en Service

**Archivo:** `app/services/inventario/productos_service.py`

```python
class InventarioProductosService:
    def listar_estados_producto(self, codigo: str) -> dict:
        """
        Obtiene todos los estados de un producto con sus cantidades.
        
        Args:
            codigo: Código del producto (S1, S2)
            
        Returns:
            Dict con id_producto y lista de estados
        """
        codigo = normalize_producto_codigo(codigo)
        
        productos = self.repository.get_all_by_codigo(codigo)
        
        if not productos:
            raise ValueError(f"Producto {codigo} no encontrado")
        
        estados = [
            {"estado": p.estado, "cantidad": p.cantidad}
            for p in productos
        ]
        
        return {
            "id_producto": codigo,
            "estados": estados
        }
```

### Paso 3: Crear Controller

**Archivo:** `app/api/inventario_productos_controller.py`

```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/productos", tags=["productos"])

@router.get("/{codigo}/estados")
def listar_estados_producto(codigo: str, db: Session = Depends(get_db)):
    """
    Obtiene todos los estados de un producto.
    
    Ejemplo:
        GET /api/productos/S1/estados
        
    Respuesta:
        {
            "id_producto": "S1",
            "estados": [
                {"estado": "Disponible", "cantidad": 100},
                {"estado": "Reservado", "cantidad": 20},
                {"estado": "A Despacho", "cantidad": 10}
            ]
        }
    """
    service = InventarioProductosService(db)
    try:
        resultado = service.listar_estados_producto(codigo)
        return resultado
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
```

### Paso 4: Probar

```bash
curl http://localhost:5050/api/productos/S1/estados

# Respuesta:
# {
#   "id_producto": "S1",
#   "estados": [
#     {"estado": "Disponible", "cantidad": 100},
#     {"estado": "Reservado", "cantidad": 0},
#     {"estado": "A Despacho", "cantidad": 0}
#   ]
# }
```

---

## Patrón 2: Agregar un Nuevo Worker Asíncrono

### Caso de Uso
Crear worker que notifique por email cuando una orden se completa.

### Paso 1: Definir Worker en tasks.py

**Archivo:** `app/tasks.py`

```python
def notificar_orden_completada(orden_id: int) -> None:
    """
    Worker que envía notificación cuando una orden se completa.
    
    Args:
        orden_id: ID de la orden completada
    """
    session = _ensure_session()
    try:
        # 1. Obtener orden
        ordenes_service = OrdenesFabricacionService(session)
        orden = ordenes_service.retrieve(orden_id)
        
        if not orden:
            print(f"[NOTIFICACION] Orden #{orden_id} no encontrada")
            return
        
        # 2. Validar estado
        if orden.estado != "completada":
            print(f"[NOTIFICACION] Orden #{orden_id} no está completada")
            return
        
        # 3. Simular envío de email (aquí iría lógica real)
        print(f"[NOTIFICACION] 📧 Enviando email para orden #{orden_id}")
        time.sleep(0.5)  # Simular latencia de servicio de email
        
        # 4. Registrar en BD que se notificó
        if isinstance(orden.detalle, dict):
            orden.detalle["notificacion_enviada"] = True
            orden.detalle["notificacion_timestamp"] = time.time()
        
        session.commit()
        print(f"[NOTIFICACION] ✓ Email enviado para orden #{orden_id}")
        
    except Exception as exc:
        print(f"[NOTIFICACION] ✗ Error en orden #{orden_id}: {exc}")
        raise
    finally:
        session.close()
```

### Paso 2: Encolar Worker desde Ingreso de Productos

**Archivo:** `app/services/inventario/productos_service.py`

Modificar método `incrementar_stock`:

```python
def incrementar_stock(self, codigo, cantidad, estado="Disponible"):
    # ... código existente ...
    
    # Completar órdenes
    for orden in ordenes_pendientes:
        if cantidad_disponible >= faltante:
            orden.estado = "completada"
            
            # ✨ NUEVO: Encolar notificación
            from app.tasks import queue, notificar_orden_completada
            queue.enqueue(notificar_orden_completada, orden.id)
```

### Paso 3: Probar

```bash
# 1. Crear orden
curl -X POST http://localhost:5050/api/fabricacion/ordenes \
  -H "Content-Type: application/json" \
  -d '{"id_producto": "S1", "cantidad": 50}'

# Respuesta: {"id": 10, "estado": "confirmado", ...}

# 2. Ingresar productos (simula fábrica terminando)
curl -X POST http://localhost:5050/api/productos/ingresos \
  -H "Content-Type: application/json" \
  -d '{"codigo": "S1", "cantidad": 50}'

# 3. Ver logs de worker
docker compose logs -f worker | grep NOTIFICACION

# Salida esperada:
# [NOTIFICACION] 📧 Enviando email para orden #10
# [NOTIFICACION] ✓ Email enviado para orden #10
```

---

## Patrón 3: Agregar una Nueva Tabla/Modelo

### Caso de Uso
Agregar tabla `alertas` para registrar alertas de stock bajo.

### Paso 1: Definir Modelo SQLAlchemy

**Archivo:** `app/models/entities.py`

```python
class Alerta(Base):
    __tablename__ = "alertas"
    
    id = Column(Integer, primary_key=True, index=True)
    id_producto = Column(String(10), nullable=False, index=True)
    tipo = Column(String(50), nullable=False)  # "stock_bajo", "stock_critico"
    mensaje = Column(Text, nullable=True)
    cantidad_actual = Column(Integer, nullable=False)
    umbral = Column(Integer, nullable=False)
    estado = Column(String(20), default="pendiente")  # "pendiente", "resuelta"
    created_at = Column(DateTime, default=datetime.utcnow)
    resuelta_at = Column(DateTime, nullable=True)
```

### Paso 2: Crear Repositorio

**Archivo:** `app/repositories/alertas_repository.py` (nuevo)

```python
from sqlalchemy.orm import Session
from app.models.entities import Alerta

class AlertasRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: dict) -> Alerta:
        """Crear nueva alerta."""
        alerta = Alerta(**data)
        self.session.add(alerta)
        self.session.commit()
        self.session.refresh(alerta)
        return alerta
    
    def get_all(self) -> list[Alerta]:
        """Obtener todas las alertas."""
        return self.session.query(Alerta).all()
    
    def get_pendientes(self) -> list[Alerta]:
        """Obtener alertas pendientes."""
        return self.session.query(Alerta)\
            .filter_by(estado="pendiente")\
            .order_by(Alerta.created_at.desc())\
            .all()
    
    def marcar_resuelta(self, alerta_id: int) -> Alerta:
        """Marcar alerta como resuelta."""
        alerta = self.session.query(Alerta).filter_by(id=alerta_id).first()
        if alerta:
            alerta.estado = "resuelta"
            alerta.resuelta_at = datetime.utcnow()
            self.session.commit()
        return alerta
```

### Paso 3: Crear Servicio

**Archivo:** `app/services/alertas_service.py` (nuevo)

```python
from app.repositories.alertas_repository import AlertasRepository

class AlertasService:
    def __init__(self, session):
        self.repository = AlertasRepository(session)
        self.session = session
    
    def crear_alerta_stock_bajo(self, codigo, cantidad_actual, umbral):
        """Crear alerta de stock bajo."""
        alerta = self.repository.create({
            "id_producto": codigo,
            "tipo": "stock_bajo",
            "mensaje": f"Stock de {codigo} bajo: {cantidad_actual} < {umbral}",
            "cantidad_actual": cantidad_actual,
            "umbral": umbral,
            "estado": "pendiente"
        })
        return alerta
    
    def listar_pendientes(self):
        """Listar alertas pendientes."""
        return self.repository.get_pendientes()
```

### Paso 4: Integrar en Flujo Existente

**Archivo:** `app/services/inventario/productos_service.py`

```python
from app.services.alertas_service import AlertasService

class InventarioProductosService:
    def transferir_stock(self, codigo, estado_origen, estado_destino, cantidad):
        # ... código existente ...
        
        # Verificar si stock disponible cayó bajo umbral
        if estado_origen == "Disponible":
            disponible = self.repository.get_by_codigo_estado(codigo, "Disponible")
            if disponible.cantidad < 500:  # Umbral
                # Crear alerta
                alertas_service = AlertasService(self.session)
                alertas_service.crear_alerta_stock_bajo(
                    codigo,
                    cantidad_actual=disponible.cantidad,
                    umbral=500
                )
```

### Paso 5: Crear Tabla en BD

```bash
# Opción 1: Recrear BD (⚠️ elimina datos)
docker compose exec api python -m app.cli create-db

# Opción 2: Ejecutar SQL manualmente
docker compose exec db psql -U postgres -d inventarios_db

# En psql:
CREATE TABLE alertas (
    id SERIAL PRIMARY KEY,
    id_producto VARCHAR(10) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    mensaje TEXT,
    cantidad_actual INTEGER NOT NULL,
    umbral INTEGER NOT NULL,
    estado VARCHAR(20) DEFAULT 'pendiente',
    created_at TIMESTAMP DEFAULT NOW(),
    resuelta_at TIMESTAMP,
    INDEX idx_producto (id_producto),
    INDEX idx_estado (estado)
);
```

---

## Patrón 4: Agregar Tests

### Caso de Uso
Testear el servicio de alertas.

### Archivo de Test

**Archivo:** `tests/test_alertas_service.py` (nuevo)

```python
import pytest
from app.services.alertas_service import AlertasService

def test_crear_alerta_stock_bajo(test_db_session):
    """Test de creación de alerta."""
    # Arrange
    service = AlertasService(test_db_session)
    
    # Act
    alerta = service.crear_alerta_stock_bajo(
        codigo="S1",
        cantidad_actual=300,
        umbral=500
    )
    
    # Assert
    assert alerta.id_producto == "S1"
    assert alerta.tipo == "stock_bajo"
    assert alerta.cantidad_actual == 300
    assert alerta.umbral == 500
    assert alerta.estado == "pendiente"

def test_listar_alertas_pendientes(test_db_session):
    """Test de listado de alertas pendientes."""
    # Arrange
    service = AlertasService(test_db_session)
    service.crear_alerta_stock_bajo("S1", 300, 500)
    service.crear_alerta_stock_bajo("S2", 200, 500)
    
    # Act
    pendientes = service.listar_pendientes()
    
    # Assert
    assert len(pendientes) == 2
    assert all(a.estado == "pendiente" for a in pendientes)
```

### Ejecutar Tests

```bash
# Opción 1: Con pytest dentro del contenedor
docker compose exec api pytest tests/test_alertas_service.py -v

# Opción 2: Localmente (requiere instalación local)
pip install -r requirements-dev.txt
pytest tests/test_alertas_service.py -v
```

---

## Mejores Prácticas

### ✅ DO

1. **Validar entrada en controllers**
   ```python
   @router.post("/productos")
   def crear_producto(body: ProductoCreate):  # Pydantic valida
       ...
   ```

2. **Lógica en services, no en controllers**
   ```python
   # ✅ BIEN
   @router.post("/reservas")
   def reservar(body, db):
       service = ProductosService(db)
       return service.reservar_stock(body.codigo, body.cantidad)
   
   # ❌ MAL
   @router.post("/reservas")
   def reservar(body, db):
       producto = db.query(...).first()  # Lógica en controller
       producto.cantidad -= body.cantidad
   ```

3. **Usar transacciones explícitas**
   ```python
   try:
       # Operaciones
       session.commit()
   except Exception:
       session.rollback()
       raise
   ```

4. **Cerrar sesiones en workers**
   ```python
   def mi_worker(id):
       session = _ensure_session()
       try:
           # Trabajo
       finally:
           session.close()
   ```

5. **Documentar funciones**
   ```python
   def procesar_orden(orden_id: int) -> None:
       """
       Procesa una orden de fabricación.
       
       Args:
           orden_id: ID de la orden
           
       Raises:
           ValueError: Si orden no existe
       """
   ```

### ❌ DON'T

1. **No mezclar lógica de negocio en controllers**
2. **No compartir sesiones entre procesos**
3. **No bloquear workers indefinidamente**
4. **No ignorar errores silenciosamente**

---

## Comandos Útiles

### Desarrollo

```bash
# Ver logs en tiempo real
docker compose logs -f api
docker compose logs -f worker

# Reiniciar servicios
docker compose restart api
docker compose restart worker

# Rebuil después de cambios de código
docker compose up --build

# Ejecutar comando en contenedor
docker compose exec api python -m app.cli <comando>

# Shell interactivo
docker compose exec api python
>>> from app.database import SessionLocal
>>> session = SessionLocal()
>>> # Experimentar...
```

### Base de Datos

```bash
# Conectar a PostgreSQL
docker compose exec db psql -U postgres -d inventarios_db

# Recrear BD (⚠️ elimina datos)
docker compose exec api python -m app.cli create-db

# Cargar datos de ejemplo
docker compose exec api python -m app.cli seed-db

# Backup
docker compose exec db pg_dump -U postgres inventarios_db > backup.sql
```

### Redis/RQ

```bash
# Conectar a Redis
docker compose exec redis redis-cli

# Ver trabajos en cola
> LLEN rq:queue:default

# Ver workers activos
> SMEMBERS rq:workers

# Limpiar cola (desarrollo)
> DEL rq:queue:default
```

---

## Errores Comunes

### Error: "Session is closed"

**Causa:** Usar sesión después de cerrarla.

**Solución:**
```python
# ❌ MAL
session = SessionLocal()
session.close()
producto = session.query(Producto).first()  # Error!

# ✅ BIEN
session = SessionLocal()
try:
    producto = session.query(Producto).first()
finally:
    session.close()
```

### Error: "Worker no procesa trabajos"

**Causa:** Worker no está corriendo o cola incorrecta.

**Solución:**
```bash
# Verificar worker
docker compose ps worker
# Estado debe ser "Up"

# Ver logs de worker
docker compose logs worker

# Si no está corriendo:
docker compose up worker
```

### Error: "Circular import"

**Causa:** Imports mutuos entre módulos.

**Solución:** Usar lazy imports

```python
# ❌ MAL: Import al inicio
from app.tasks import queue

# ✅ BIEN: Import dentro de función
def mi_funcion():
    from app.tasks import queue
    queue.enqueue(...)
```

---

## Recursos

### Documentación Externa
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [RQ Docs](https://python-rq.org/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Pydantic Docs](https://docs.pydantic.dev/)

### Documentación Interna
- [00_INDICE.md](00_INDICE.md) - Índice de documentación
- [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md) - Arquitectura
- [02_SISTEMA_COLAS.md](02_SISTEMA_COLAS.md) - Sistema de colas
- [TESTING.md](TESTING.md) - Guía de testing

---

## Próximos Pasos

1. **Prueba los patrones:** Implementa los ejemplos de esta guía
2. **Lee el código fuente:** Explora `app/` para ver más ejemplos
3. **Ejecuta los tests:** `pytest tests/ -v`
4. **Contribuye:** Crea un PR con tu nueva funcionalidad

¡Happy coding! 🚀
