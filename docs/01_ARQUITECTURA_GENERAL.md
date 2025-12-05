# 🏗️ Arquitectura General del Sistema

## Visión General

Este es un **microservicio de inventario** construido con FastAPI que gestiona productos, piezas, proveedores y órdenes de fabricación. El sistema utiliza **procesamiento asíncrono** mediante colas de trabajo (Redis + RQ) para manejar tareas que requieren tiempo sin bloquear la API.

## Diagrama de Arquitectura Completa

```mermaid
graph TB
    subgraph "Cliente"
        CLIENT[Cliente HTTP]
    end

    subgraph "Docker Compose"
        subgraph "Contenedor API"
            API[FastAPI + Uvicorn<br/>Puerto 5050]
            CONTROLLERS[Controllers<br/>app/api/]
            SERVICES[Services<br/>app/services/]
            REPOS[Repositories<br/>app/repositories/]
        end

        subgraph "Contenedor Worker"
            WORKER[RQ Worker]
            TASKS[Task Functions<br/>app/tasks.py]
        end

        subgraph "Contenedor Redis"
            REDIS[(Redis Queue<br/>Puerto 6379)]
        end

        subgraph "Contenedor PostgreSQL"
            DB[(PostgreSQL 15<br/>Puerto 5434)]
        end
    end

    CLIENT -->|HTTP Request| API
    API --> CONTROLLERS
    CONTROLLERS --> SERVICES
    SERVICES --> REPOS
    REPOS --> DB

    SERVICES -->|queue.enqueue()| REDIS
    REDIS -->|Consume jobs| WORKER
    WORKER --> TASKS
    TASKS --> REPOS
    REPOS --> DB

    API -->|Respuesta rápida| CLIENT
    WORKER -.->|Actualiza estado| DB
```

## Componentes Principales

### 1. API (FastAPI + Uvicorn)

**Responsabilidades:**
- Recibir solicitudes HTTP
- Validar datos de entrada (Pydantic)
- Orquestar servicios
- Encolar trabajos pesados en Redis
- Responder rápidamente al cliente

**Puerto:** 5050 (expuesto), 5000 (interno)

**Tecnologías:**
- FastAPI (framework)
- Uvicorn (ASGI server)
- Pydantic (validación)
- SQLAlchemy (ORM)

**Código:** `app/api/*.py`

### 2. Worker (RQ)

**Responsabilidades:**
- Consumir trabajos de la cola Redis
- Ejecutar tareas en background
- Actualizar base de datos con resultados
- Manejar errores y reintentos

**Proceso:** Separado del API container

**Tecnologías:**
- RQ (Redis Queue)
- Redis (broker)

**Código:** `app/tasks.py`

**Workers definidos:**
- `procesar_solicitud_pieza`: Simula pedido a proveedor
- `procesar_orden_fabricacion`: Consume piezas de órdenes confirmadas

### 3. Redis

**Responsabilidades:**
- Almacenar cola de trabajos
- Comunicar API ↔ Workers
- Persistir estado de trabajos

**Puerto:** 6379

**Cola:** `default`

### 4. PostgreSQL

**Responsabilidades:**
- Persistir datos (productos, piezas, proveedores, órdenes, solicitudes)
- Fuente de verdad compartida entre API y Workers
- Transacciones ACID

**Puerto:** 5434 (expuesto vía `HOST_POSTGRES_PORT`), 5432 (interno)

**Tablas principales:**
- `inventario_productos`
- `inventario_piezas`
- `proveedores`
- `ordenes_fabricacion`
- `solicitudes_pieza`
- `movimientos`

## Arquitectura por Capas

El código sigue una arquitectura en capas para separar responsabilidades:

```
┌─────────────────────────────────────────┐
│  API Layer (app/api/)                   │  ← Controllers FastAPI
│  - Recibe requests HTTP                 │
│  - Valida con Pydantic                  │
│  - Delega a Service Layer               │
└─────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│  Service Layer (app/services/)          │  ← Lógica de negocio
│  - Reglas de negocio                    │
│  - Orquestación                         │
│  - Encolado de trabajos                 │
└─────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│  Repository Layer (app/repositories/)   │  ← Acceso a datos
│  - CRUD operations                      │
│  - Queries SQLAlchemy                   │
│  - Abstracción de BD                    │
└─────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│  Domain Layer (app/domain/)             │  ← Lógica pura
│  - Constantes                           │
│  - Normalizadores                       │
│  - Planes sin I/O                       │
└─────────────────────────────────────────┘
```

### Ventajas de esta arquitectura:
- ✅ **Separación de responsabilidades**: Cada capa tiene un propósito claro
- ✅ **Testabilidad**: Servicios inyectables y mockeables
- ✅ **Mantenibilidad**: Cambios en una capa no afectan otras
- ✅ **Escalabilidad**: Capas pueden optimizarse independientemente

## Organización de Servicios por Dominio

Los servicios están organizados por dominios de negocio:

```
app/services/
├── inventario/
│   ├── productos_service.py              # Gestión de productos
│   ├── piezas_service.py                 # Gestión de piezas
│   ├── movimientos_service.py            # Registro de movimientos
│   └── productos_manufacturing_helper.py # Helper de fabricación
├── fabricacion/
│   ├── fabricacion_service.py            # Planes de fabricación
│   ├── ordenes_service.py                # Órdenes de fabricación
│   ├── entregas_service.py               # Acumulación de entregas
│   └── fabricacion_orchestrator.py       # Orquestador de órdenes
└── proveedores/
    ├── proveedores_service.py            # Gestión de proveedores
    └── solicitudes_service.py            # Solicitudes de piezas
```

### Dominio: Inventario
Gestiona el inventario de productos terminados y piezas.

**Productos:**
- Códigos: `S1`, `S2`
- Estados: `Disponible`, `Reservado`, `A Despacho`
- Operaciones: transferencias, reservas, despachos, ingresos

**Piezas:**
- IDs: `P1`, `P2`, `P3`, `P4`, `P5`, `P6`
- Vinculadas a proveedores
- Consumidas durante fabricación

### Dominio: Fabricación
Coordina la producción de productos.

**Responsabilidades:**
- Calcular materiales necesarios
- Verificar disponibilidad de piezas
- Confirmar fabricación con servicio externo
- Consumir piezas del inventario
- Completar órdenes cuando llegan productos

### Dominio: Proveedores
Gestiona proveedores y solicitudes de piezas.

**Responsabilidades:**
- CRUD de proveedores
- Solicitudes síncronas (respuesta inmediata)
- Solicitudes asíncronas (encoladas con RQ)

## Flujo de Datos

### Flujo Síncrono (Respuesta inmediata)

```
Cliente → API → Service → Repository → DB
                                          ↓
Cliente ← API ← Service ← Repository ← Query Result
```

**Ejemplo:** `GET /api/productos`
1. Cliente hace request
2. Controller llama a `ProductosService.list()`
3. Service llama a `ProductosRepository.get_all()`
4. Repository consulta PostgreSQL
5. Datos regresan por la cadena
6. API responde JSON al cliente

**Tiempo de respuesta:** ~10-100ms

### Flujo Asíncrono (Con cola)

```
Cliente → API → Service → queue.enqueue() → Redis
         ↓                                    ↓
    Respuesta                            Worker consume
    inmediata                                 ↓
                                    Ejecuta tarea → DB
```

**Ejemplo:** `POST /api/proveedores/solicitudes_async`
1. Cliente hace request
2. Service crea registro de solicitud
3. Service encola trabajo: `queue.enqueue(procesar_solicitud_pieza, solicitud_id)`
4. API responde inmediatamente: `{"id": 1, "estado": "pendiente"}`
5. Worker RQ consume el trabajo de Redis
6. Worker ejecuta `procesar_solicitud_pieza()`
7. Worker actualiza solicitud a `"completada"` y suma piezas

**Tiempo de respuesta API:** ~50-200ms  
**Tiempo total de procesamiento:** Depende del worker

## Patrones de Diseño Aplicados

### 1. Repository Pattern
Abstrae el acceso a datos.

```python
# app/repositories/productos_repository.py
class InventarioProductosRepository:
    def get_by_codigo_estado(self, codigo, estado):
        return self.session.query(InventarioProducto)\
            .filter_by(id_producto=codigo, estado=estado).first()
```

**Ventajas:**
- Cambiar ORM sin afectar servicios
- Testing con mocks más fácil

### 2. Service Layer Pattern
Encapsula lógica de negocio.

```python
# app/services/inventario/productos_service.py
class InventarioProductosService:
    def reservar_stock(self, codigo, cantidad):
        # Reglas de negocio aquí
        disponible = self.repo.get_by_codigo_estado(codigo, "Disponible")
        if disponible.cantidad < cantidad:
            # Lógica de fabricación
```

### 3. Dependency Injection
Servicios reciben dependencias por constructor.

```python
class ProductosService:
    def __init__(self, session, piezas_repository=None):
        self.session = session
        self.piezas_repo = piezas_repository or InventarioPiezasRepository(session)
```

**Ventajas:**
- Testing con mocks
- Flexibilidad

### 4. Producer-Consumer (Colas)
API produce trabajos, Workers consumen.

```python
# Producer (API)
queue.enqueue(procesar_solicitud_pieza, solicitud_id)

# Consumer (Worker)
def procesar_solicitud_pieza(solicitud_id):
    # Procesar trabajo
```

## Gestión de Estado

### Estados de Solicitudes de Pieza
```
pendiente → en_proceso → completada
                      ↘ fallida
```

### Estados de Órdenes de Fabricación
```
calculando → confirmando → confirmado → consumiendo_piezas → 
    esperando_fabricacion → completada
         ↓
   confirmacion_fallida → fallida
```

### Estados de Inventario de Productos
```
Disponible ←→ Reservado ←→ A Despacho
     ↑                          ↓
     └─────── (despacho) ───────┘
```

## Transacciones y Consistencia

### Transacciones en API
```python
@router.post("/api/productos/transferencias")
def transferir(body, db: Session):
    service = ProductosService(db)
    resultado = service.transferir_stock(...)
    # Session.commit() se hace en el servicio
    return resultado
```

### Transacciones en Workers
```python
def procesar_solicitud_pieza(solicitud_id):
    session = _ensure_session()
    try:
        # Múltiples updates
        solicitud.estado = "en_proceso"
        session.commit()
        # ... más trabajo ...
        pieza.cantidad += solicitud.cantidad
        session.commit()
    finally:
        session.close()
```

## Escalabilidad

### Escalado Horizontal

**API:**
```bash
# docker-compose.yml
services:
  api:
    deploy:
      replicas: 3  # 3 instancias de API
```

**Workers:**
```bash
# docker-compose.yml
services:
  worker:
    deploy:
      replicas: 5  # 5 workers procesando en paralelo
```

### Escalado Vertical
- Aumentar recursos de contenedores
- Configurar pool de conexiones PostgreSQL

## Manejo de Errores

### En API
```python
try:
    resultado = service.hacer_algo()
    return resultado
except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc))
```

### En Workers
```python
def procesar_orden_fabricacion(orden_id):
    try:
        # Procesamiento
    except Exception as exc:
        orden.estado = "fallida"
        orden.detalle = {"error": str(exc)}
        session.commit()
```

## Monitoreo y Logging

### Logs de API
```bash
docker compose logs -f api
```

### Logs de Workers
```bash
docker compose logs -f worker
```

### Inspeccionar Redis
```bash
docker compose exec redis redis-cli
> LLEN rq:queue:default  # Ver cantidad de trabajos en cola
> KEYS rq:*              # Ver todas las keys de RQ
```

## Archivos de Configuración Clave

| Archivo | Propósito |
|---------|-----------|
| `docker-compose.yml` | Orquestación de contenedores |
| `.env` | Variables de entorno |
| `app/__init__.py` | Inicialización de FastAPI |
| `app/database.py` | Configuración de SQLAlchemy |
| `app/routes.py` | Registro de routers |
| `app/tasks.py` | Definición de workers |
| `main.py` | Entry point de la aplicación |

## Próximos Pasos

Ahora que entiendes la arquitectura general:

1. **Profundiza en colas:** Lee [02_SISTEMA_COLAS.md](02_SISTEMA_COLAS.md)
2. **Entiende concurrencia:** Lee [03_PARALELISMO_CONCURRENCIA.md](03_PARALELISMO_CONCURRENCIA.md)
3. **Aprende los flujos:** Lee [04_FLUJOS_INVENTARIO.md](04_FLUJOS_INVENTARIO.md)
4. **Empieza a desarrollar:** Lee [05_GUIA_DESARROLLO.md](05_GUIA_DESARROLLO.md)
