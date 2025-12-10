# Microservicio de Inventarios

Sistema de gestión de inventarios construido con **FastAPI**, **Redis**, **RQ** y **PostgreSQL**. Utiliza **procesamiento asíncrono** mediante colas de trabajo para manejar operaciones que requieren tiempo sin bloquear la API.

> 📚 **Documentación completa:** Ver [00_INDICE.md](00_INDICE.md) para guías detalladas

## 🌟 Características

- ✅ **API REST** con FastAPI (endpoints JSON)
- ✅ **Procesamiento asíncrono** con Redis + RQ
- ✅ **Gestión de inventario** de productos y piezas
- ✅ **Órdenes de fabricación** con consumo automático de piezas  
- ✅ **Solicitudes a proveedores** síncronas y asíncronas
- ✅ **Multi-estado de productos** (Disponible, Reservado, A Despacho)
- ✅ **Escalabilidad horizontal** (workers paralelos)
- ✅ **Docker Compose** para desarrollo local

## 🏗️ Stack Tecnológico

| Componente | Tecnología | Puerto | Propósito |
|------------|------------|--------|-----------|
| **API** | FastAPI + Uvicorn | 5050 | Endpoints REST |
| **Worker** | RQ (Redis Queue) | - | Procesamiento asíncrono |
| **Cola** | Redis 7 | 6379 | Broker de mensajes |
| **Base de datos** | PostgreSQL 15 | 5434 (HOST_POSTGRES_PORT) | Persistencia |

## 🚀 Quick Start

### 1. Levantar Servicios

```bash
# Clonar repositorio
git clone <repo_url>
cd Proyecto-Infraestructuras-Inventario

# Copiar variables de entorno
cp .env.example .env

# Levantar todo con Docker Compose
# Si tienes otro Postgres ocupando el puerto, ajusta HOST_POSTGRES_PORT en .env
docker compose up --build
```

### 2. Inicializar Base de Datos

```bash
# Crear tablas
docker compose exec api python -m app.cli create-db

# Cargar datos de ejemplo
docker compose exec api python -m app.cli seed-db
```

### 3. Probar Endpoints

```bash
# Health check
curl http://localhost:5050/health

# Listar productos
curl http://localhost:5050/api/productos

# Listar piezas
curl http://localhost:5050/api/piezas

# Documentación interactiva
open http://localhost:5050/docs
```

## 📊 Arquitectura

```
┌─────────────┐   HTTP    ┌──────────┐
│   Cliente   │ ────────► │   API    │
└─────────────┘           │ FastAPI  │
                          └────┬─────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          │
                    ▼          ▼          ▼
              ┌─────────┐ ┌────────┐ ┌────────┐
              │  Redis  │ │ Worker │ │Postgres│
              │  Queue  │ │   RQ   │ │   DB   │
              └─────────┘ └────────┘ └────────┘
```

**Flujo asíncrono:**
1. Cliente → API: Request HTTP
2. API → Redis: Encolar trabajo
3. API → Cliente: Respuesta rápida (202 Accepted)
4. Worker → Redis: Consumir trabajo
5. Worker → PostgreSQL: Actualizar datos

> 📖 **Más detalles:** [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md)

## 📦 Recursos Principales

### Inventario de Productos

**Productos:** `S1`, `S2`  
**Estados:** `Disponible`, `Reservado`, `A Despacho`

**Endpoints clave:**
```bash
# Listar todos los productos
GET /api/productos

# Ver estados de un producto
GET /api/productos/S1

# Ver un estado específico
GET /api/productos/S1/Disponible

# Transferir entre estados
POST /api/productos/transferencias
{
  "id_producto": "S1",
  "estado_origen": "Disponible",
  "estado_destino": "Reservado",
  "cantidad": 50
}

# Ingresar stock (aumentar cantidad)
POST /api/productos/ingresos
{
  "codigo": "S1",
  "cantidad": 100,
  "estado": "Disponible"
}

# Reservar stock (VENTAS)
POST /api/productos/reservas
{
  "id_producto": "S1",
  "cantidad": 50
}

# Despachar productos
POST /api/productos/despachos
{
  "id_producto": "S1",
  "cantidad": 50
}
```

### Inventario de Piezas

**Piezas:** `P1`, `P2`, `P3`, `P4`, `P5`, `P6`  
Cada pieza está vinculada a un proveedor.

**Endpoints clave:**
```bash
# Listar piezas
GET /api/piezas

# Crear pieza
POST /api/piezas
{
  "id_pieza": 7,
  "nombre": "Motor",
  "cantidad": 100,
  "id_proveedor": 1
}

# Actualizar pieza
PUT /api/piezas/7
{
  "cantidad": 150
}

# Eliminar pieza
DELETE /api/piezas/7
```

### Proveedores

**Proveedores:** `Prov1` a `Prov6`  
Cada proveedor tiene un tiempo de entrega.

**Endpoints clave:**
```bash
# Listar proveedores
GET /api/proveedores

# Solicitud síncrona (respuesta inmediata)
POST /api/proveedores/solicitudes
{
  "id_pieza": 1,
  "cantidad": 100
}

# Solicitud asíncrona (procesamiento en background)
POST /api/proveedores/solicitudes_async
{
  "id_pieza": 1,
  "cantidad": 100
}
# Respuesta: {"id": 5, "estado": "pendiente"}

# Consultar estado de solicitud async
GET /api/proveedores/solicitudes_async/5
# Respuesta: {"id": 5, "estado": "completada", ...}
```

### Órdenes de Fabricación

Coordina producción de productos consumiendo piezas del inventario.

**Endpoints clave:**
```bash
# Crear orden de fabricación
POST /api/fabricacion/ordenes
{
  "id_producto": "S1",
  "cantidad": 100
}
# Respuesta: {"id": 25, "estado": "confirmado", "tiempo_estimado": 9}

# Listar órdenes
GET /api/fabricacion/ordenes

# Ver orden específica
GET /api/fabricacion/ordenes/25

# Calcular piezas necesarias
POST /api/fabricacion/calcular_piezas
{
  "codigo": "S1",
  "cantidad": 100
}
# (El cálculo de piezas lo hace la fábrica; evitar el antiguo GET /api/fabricacion/plan)
```

## 🔄 Sistema de Colas (Redis + RQ)

El sistema utiliza **workers asíncronos** para procesar tareas pesadas sin bloquear la API.

### Workers Disponibles

1. **procesar_solicitud_pieza**: Simula pedido a proveedor
2. **procesar_orden_fabricacion**: Consume piezas de órdenes confirmadas

### Ejemplo: Solicitud Asíncrona

```bash
# 1. Cliente solicita piezas (API responde inmediatamente)
curl -X POST http://localhost:5050/api/proveedores/solicitudes_async \
  -H "Content-Type: application/json" \
  -d '{"id_pieza": 1, "cantidad": 100}'

# Respuesta en ~50ms:
# {"id": 5, "estado": "pendiente", "tiempo_estimado": 0}

# 2. Worker procesa en background (5 segundos)
# [WORKER] Procesando solicitud #5
# [WORKER] Incrementando pieza #1: +100 unidades
# [WORKER] Solicitud #5 completada ✓

# 3. Cliente consulta estado
curl http://localhost:5050/api/proveedores/solicitudes_async/5

# Respuesta:
# {"id": 5, "id_pieza": 1, "cantidad": 100, "estado": "completada"}
```

**Ventajas:**
- ✅ API responde en ~50ms (no espera worker)
- ✅ Workers procesan en paralelo
- ✅ Escalabilidad horizontal

> 📖 **Más detalles:** [02_SISTEMA_COLAS.md](02_SISTEMA_COLAS.md)

## ⚡ Paralelismo y Concurrencia

### API + Workers en Paralelo

```
Timeline de Ejecución:

API      │ Request 1 │ Request 2 │ Request 3 │
         │  (50ms)   │  (50ms)   │  (50ms)   │
         └─enqueue───┴─enqueue───┴─enqueue───

Worker1  │═══════ Solicitud #1 (5s) ═══════│
Worker2         │═══════ Solicitud #2 (5s) ═══════│
Worker3                │═══ Orden #3 (3s) ═══│
```

**API y Workers ejecutan simultáneamente** sin bloquearse mutuamente.

### Escalado Horizontal

```yaml
# docker-compose.yml
services:
  worker:
    deploy:
      replicas: 10  # 10 workers procesando en paralelo
```

**Resultado:** Throughput 10x mayor

> 📖 **Más detalles:** [03_PARALELISMO_CONCURRENCIA.md](03_PARALELISMO_CONCURRENCIA.md)

## 📋 Flujos de Negocio

### Flujo 1: Solicitud de Pieza Asíncrona
```
Usuario → API → Redis → Worker → Actualiza inventario
   ↓ (inmediato)         ↓ (background)
Respuesta 202
```

### Flujo 2: Orden de Fabricación
```
Usuario → API → Calcular piezas → Solicitar faltantes →
          Confirmar fábrica → Encolar worker →
          Worker consume piezas → Espera productos
```

### Flujo 3: Ingreso de Productos
```
Productos listos → API → Incrementa inventario →
                   Completa órdenes pendientes automáticamente
```

> 📖 **Más detalles:** [04_FLUJOS_INVENTARIO.md](04_FLUJOS_INVENTARIO.md)

## 🛠️ Comandos Útiles

### Desarrollo

```bash
# Logs en tiempo real
docker compose logs -f api
docker compose logs -f worker

# Reiniciar servicios
docker compose restart api worker

# Rebuild después de cambios
docker compose up --build

# Ejecutar tests
docker compose exec api pytest tests/ -v
```

### Base de Datos

```bash
# Conectar a PostgreSQL
docker compose exec db psql -U postgres -d inventarios_db

# Recrear BD (⚠️ elimina datos)
docker compose exec api python -m app.cli create-db

# Hacer backup
docker compose exec db pg_dump -U postgres inventarios_db > backup.sql
```

### Redis/Colas

```bash
# Conectar a Redis
docker compose exec redis redis-cli

# Ver trabajos en cola
> LLEN rq:queue:default

# Ver workers activos
> SMEMBERS rq:workers
```

## 📁 Estructura del Proyecto

```
app/
├── api/                # Controllers FastAPI
│   ├── inventario_productos_controller.py
│   ├── inventario_piezas_controller.py
│   ├── proveedores_controller.py
│   ├── movimientos_controller.py
│   └── fabricacion_controller.py
├── services/           # Lógica de negocio (por dominio)
│   ├── inventario/     # Productos, piezas, movimientos
│   ├── fabricacion/    # Órdenes, planes, entregas
│   └── proveedores/    # Proveedores, solicitudes
├── repositories/       # Acceso a datos (CRUD)
├── models/             # Modelos SQLAlchemy
├── schemas/            # Modelos Pydantic (validación)
├── domain/             # Lógica pura (constantes, normalizadores)
├── core/               # Utilidades transversales
├── data/seed/          # Datos de ejemplo (JSON)
├── tasks.py            # Workers RQ
├── database.py         # Configuración SQLAlchemy
└── routes.py           # Registro de routers
```

## 🧪 Testing

```bash
# Ejecutar todos los tests
docker compose exec api pytest

# Ejecutar con verbosity
docker compose exec api pytest -v

# Ejecutar test específico
docker compose exec api pytest tests/test_productos.py

# Ver coverage
docker compose exec api pytest --cov=app tests/
```

> 📖 **Más detalles:** [TESTING.md](TESTING.md)

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| [00_INDICE.md](00_INDICE.md) | 🗺️ Índice de documentación |
| [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md) | 🏗️ Arquitectura completa |
| [02_SISTEMA_COLAS.md](02_SISTEMA_COLAS.md) | 🔄 Redis + RQ en detalle |
| [03_PARALELISMO_CONCURRENCIA.md](03_PARALELISMO_CONCURRENCIA.md) | ⚡ Concurrencia y escalado |
| [04_FLUJOS_INVENTARIO.md](04_FLUJOS_INVENTARIO.md) | 📊 Diagramas de flujos |
| [05_GUIA_DESARROLLO.md](05_GUIA_DESARROLLO.md) | 🛠️ Cómo extender el sistema |
| [TESTING.md](TESTING.md) | 🧪 Guía de pruebas |

## 🌐 Variables de Entorno

```bash
# .env
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/inventarios_db
REDIS_URL=redis://redis:6379/0
POSTGRES_DB=inventarios_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

## 🎯 Próximos Pasos

### Nuevo en el Proyecto
1. Lee [00_INDICE.md](00_INDICE.md) - Guía de navegación
2. Lee [01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md) - Entiende el sistema
3. Lee [02_SISTEMA_COLAS.md](02_SISTEMA_COLAS.md) - Aprende colas
4. Prueba los endpoints con `curl` o desde `/docs`

### Listo para Desarrollar
1. Lee [05_GUIA_DESARROLLO.md](05_GUIA_DESARROLLO.md) - Patrones y ejemplos
2. Explora el código en `app/`
3. Ejecuta los tests: `pytest`
4. ¡Crea tu primera funcionalidad!

---

**Desarrollado con ❤️ usando FastAPI, Redis, RQ y PostgreSQL**
