# Documentación de Endpoints - Sistema de Inventario y Ventas

## Tabla de Contenidos
1. [🛒 VENTAS](#-ventas)
2. [📦 DESPACHOS](#-despachos)
3. [🏭 FÁBRICA](#-fábrica)
4. [⚙️ Configuración Técnica](#️-configuración-técnica)

---

# 🛒 VENTAS

Esta sección documenta todos los endpoints relacionados con el proceso de ventas, desde la consulta de productos hasta la confirmación de retiros.

## 1.1 Endpoints que Exponemos

### API de Ventas (Express.js/TypeScript)
**Base URL**: `http://localhost:3000`
**Puerto**: 3000

#### Ventas (`/api/sales`)

| Método | Endpoint | Descripción | Uso |
|--------|----------|-------------|-----|
| `POST` | `/api/sales` | Crear nueva venta | Frontend → API Ventas |
| `GET` | `/api/sales` | Listar todas las ventas | Frontend → API Ventas |
| `GET` | `/api/sales/:id` | Obtener venta específica | Frontend → API Ventas |
| `GET` | `/api/sales/products` | Listar productos (proxy a Inventario) | Frontend → API Ventas |
| `PATCH` | `/api/sales/:id/complete` | Completar venta pendiente | Frontend → API Ventas |
| `POST` | `/api/sales/cleanup-expired` | Limpiar ventas expiradas | Proceso interno |
| `POST` | `/api/sales/check-delivery` | Verificar disponibilidad de entrega | Frontend → API Ventas |

#### Personas/Clientes (`/api/persons`)

| Método | Endpoint | Descripción | Uso |
|--------|----------|-------------|-----|
| `POST` | `/api/persons` | Crear persona | Frontend → API Ventas |
| `GET` | `/api/persons` | Listar personas | Frontend → API Ventas |
| `GET` | `/api/persons/:id` | Obtener persona específica | Frontend → API Ventas |
| `PUT` | `/api/persons/:id` | Actualizar persona | Frontend → API Ventas |
| `DELETE` | `/api/persons/:id` | Eliminar persona | Frontend → API Ventas |

---

### API de Inventario - Integración de Ventas (FastAPI)
**Base URL**: `http://localhost:3001`
**Puerto**: 3001

#### Integración de Ventas v1 (`/api/v1`)

| Método | Endpoint | Descripción | Consumido por |
|--------|----------|-------------|---------------|
| `GET` | `/api/v1/products` | Listar productos con catálogo | ⭐ API Ventas |
| `GET` | `/api/v1/products/search` | Buscar productos | ⭐ API Ventas |
| `GET` | `/api/v1/products/{product_id}` | Obtener producto específico | ⭐ API Ventas |
| `GET` | `/api/v1/products/{product_id}/availability` | Verificar disponibilidad | ⭐ API Ventas |
| `POST` | `/api/v1/reservations` | Crear reservación | ⭐ API Ventas |
| `POST` | `/api/v1/reservations/{reservation_id}/confirm` | Confirmar reservación | ⭐ API Ventas |
| `DELETE` | `/api/v1/reservations/{reservation_id}` | Liberar reservación | ⭐ API Ventas |

⭐ = Endpoints consumidos por la API de Ventas

#### Productos - Operaciones de Venta (`/api/productos`)

| Método | Endpoint | Descripción | Consumido por |
|--------|----------|-------------|---------------|
| `POST` | `/api/productos/reservas` | Reservar productos para venta | ⭐ API Ventas |
| `POST` | `/api/productos/retiros` | Confirmar retiro local (pickup) | ⭐ API Ventas |
| `POST` | `/api/productos/pedidos/online` | Procesar pedido online | Sistemas externos |
| `POST` | `/api/productos/pedidos/local` | Procesar pedido local | Sistemas externos |
| `GET` | `/api/productos/pedidos` | Listar pedidos de venta | Consulta |
| `POST` | `/api/productos/pedidos/reset` | Resetear pedidos | Administración |

---

## 1.2 Endpoints Externos que Consumimos

### API de Inventario (consumida desde API de Ventas)
**Archivo**: `backend/src/controllers/salesController.ts`
**Método HTTP**: `axios`
**Base URL**: `${INVENTORY_API_URL}` (default: `http://localhost:3001`)

| Método | Endpoint | Propósito |
|--------|----------|-----------|
| `POST` | `/api/productos/reservas` | Reservar productos para una venta |
| `POST` | `/api/productos/retiros` | Confirmar retiro de productos (pickup) |
| `GET` | `/api/v1/products` | Listar productos disponibles |
| `GET` | `/api/v1/products/search?query={term}` | Buscar productos por término |
| `GET` | `/api/v1/products/{productId}` | Obtener detalles de un producto |
| `GET` | `/api/v1/products/{productId}/availability` | Verificar disponibilidad de producto |
| `POST` | `/api/v1/reservations` | Crear reservación de producto |
| `POST` | `/api/v1/reservations/{id}/confirm` | Confirmar reservación |
| `DELETE` | `/api/v1/reservations/{id}` | Liberar/cancelar reservación |

---

## 1.3 Flujo de Ventas

### Flujo: Crear Venta

```
┌─────────────┐      POST /api/sales      ┌──────────────────┐
│   Frontend  │ ─────────────────────────> │  Backend Ventas  │
│   (React)   │                            │   (Express.js)   │
└─────────────┘                            └──────────────────┘
                                                     │
                      ┌──────────────────────────────┼──────────────────────────────┐
                      │                              │                              │
                      ▼                              ▼                              ▼
         POST /api/productos/reservas    POST /api/despachos         Guardar en PostgreSQL
         POST /api/productos/retiros      (si tipo = DISPATCH)              (sales_db)
              ┌─────────────┐               ┌─────────────┐
              │ API         │               │ API         │
              │ Inventario  │               │ Dispatch    │
              └─────────────┘               └─────────────┘
```

### Flujo: Consultar Disponibilidad de Productos

```
┌─────────────┐  GET /api/sales/products  ┌──────────────────┐
│   Frontend  │ ────────────────────────> │  Backend Ventas  │
└─────────────┘                            └──────────────────┘
                                                     │
                                                     ▼
                                         GET /api/v1/products
                                            ┌─────────────┐
                                            │ API         │
                                            │ Inventario  │
                                            └─────────────┘
                                                     │
                                                     ▼
                                            PostgreSQL (inventarios_db)
```

---

# 📦 DESPACHOS

Esta sección documenta todos los endpoints relacionados con el proceso de despacho y entrega de productos.

## 2.1 Endpoints que Exponemos

### API de Inventario - Operaciones de Despacho (FastAPI)
**Base URL**: `http://localhost:3001`

#### Productos - Despachos (`/api/productos`)

| Método | Endpoint | Descripción | Consumido por |
|--------|----------|-------------|---------------|
| `POST` | `/api/productos/despachos` | Despachar productos para venta | ⭐ API Ventas |
| `POST` | `/api/productos/despachos/descontar` | Descontar estado A Despacho | Procesos internos |
| `POST` | `/api/productos/ordenes/{orden_id}/entregas` | Registrar entrega de orden | API Despacho |

⭐ = Endpoints consumidos por la API de Ventas

---

## 2.2 Endpoints Externos que Consumimos

### API de Despacho/Dispatch (consumida desde API de Ventas)
**Archivo**: `backend/src/services/dispatchService.ts`
**Método HTTP**: `axios`
**Base URL**: `${DISPATCH_API_URL}` (default: `http://localhost:3002`)

| Método | Endpoint | Propósito |
|--------|----------|-----------|
| `POST` | `/api/dispatch/check-availability` | Verificar disponibilidad de despacho |
| `POST` | `/api/despachos` | Crear orden de despacho |
| `GET` | `/api/dispatch/{dispatchId}` | Obtener estado de un despacho |

---

## 2.3 Flujo de Despachos

### Flujo: Crear Orden de Despacho

```
┌──────────────────┐   POST /api/sales    ┌──────────────────┐
│  Frontend Ventas │ ──────────────────> │  Backend Ventas  │
└──────────────────┘                      └──────────────────┘
                                                   │
                                                   ▼
                                   POST /api/dispatch/check-availability
                                          ┌─────────────┐
                                          │ API         │
                                          │ Dispatch    │
                                          └─────────────┘
                                                   │
                                                   ▼
                                          POST /api/despachos
                                          (crear orden)
                                                   │
                                                   ▼
                                   POST /api/productos/despachos
                                          ┌─────────────┐
                                          │ API         │
                                          │ Inventario  │
                                          └─────────────┘
```

---

# 🏭 FÁBRICA

Esta sección documenta todos los endpoints relacionados con el proceso de fabricación, producción y gestión de piezas.

## 3.1 Endpoints que Exponemos

### API de Inventario - Fabricación (FastAPI)
**Base URL**: `http://localhost:3001`

#### Fabricación (`/api/fabricacion`)

| Método | Endpoint | Descripción | Tipo |
|--------|----------|-------------|------|
| `GET` | `/api/fabricacion/plan/{codigo}` | Obtener plan de fabricación | Consulta |
| `POST` | `/api/fabricacion/calcular_piezas` | Calcular piezas necesarias | Operación |
| `POST` | `/api/fabricacion/producciones` | Producir lote | Operación |
| `POST` | `/api/fabricacion/ordenes` | Crear orden de fabricación (202 Accepted) | Operación asíncrona |
| `GET` | `/api/fabricacion/ordenes/{orden_id}` | Obtener orden específica | Consulta |
| `GET` | `/api/fabricacion/ordenes` | Listar órdenes | Consulta |
| `POST` | `/api/fabricacion/ordenes/reset` | Resetear órdenes | Administración |
| `GET` | `/api/fabricacion/external/status` | Verificar estado servicio externo | Monitoreo |
| `GET` | `/api/fabricacion/external/config` | Obtener configuración externa | Configuración |
| `POST` | `/api/fabricacion/external/config` | Actualizar configuración externa | Configuración |
| `GET` | `/api/fabricacion/external/planos/{plano_id}` | Obtener plano externo (proxy) | Proxy |
| `POST` | `/api/fabricacion/webhook/productos_terminados` | Webhook de productos fabricados 🔔 | Webhook |

🔔 = Webhook para recibir notificaciones de API Externa de Fabricación

#### Piezas (`/api/piezas`)

| Método | Endpoint | Descripción | Tipo |
|--------|----------|-------------|------|
| `GET` | `/api/piezas` | Listar todas las piezas | Consulta |
| `GET` | `/api/piezas/{pieza_id}` | Obtener pieza específica | Consulta |
| `POST` | `/api/piezas` | Crear pieza | Operación |
| `DELETE` | `/api/piezas/{pieza_id}` | Eliminar pieza | Operación |
| `POST` | `/api/piezas/reset` | Resetear todas las piezas | Administración |
| `PUT` | `/api/piezas/{pieza_id}` | Actualizar pieza | Operación |

#### Productos (`/api/productos`)

| Método | Endpoint | Descripción | Tipo |
|--------|----------|-------------|------|
| `GET` | `/api/productos` | Listar todos los productos | Consulta |
| `GET` | `/api/productos/pendientes` | Listar productos en estado Pendiente | Consulta |
| `GET` | `/api/productos/{producto_id}` | Obtener estados de un producto | Consulta |
| `GET` | `/api/productos/{producto_id}/{estado}` | Obtener cantidad en estado específico | Consulta |
| `POST` | `/api/productos` | Crear producto | Operación |
| `DELETE` | `/api/productos/{producto_id}/{estado}` | Eliminar producto | Operación |
| `POST` | `/api/productos/reset` | Resetear todos los productos | Administración |
| `PUT` | `/api/productos/{producto_id}/{estado}` | Actualizar cantidad de producto | Operación |
| `POST` | `/api/productos/ingresos` | Incrementar cantidad (INGRESO) | Operación |
| `POST` | `/api/productos/transferencias` | Transferir entre estados | Operación |
| `POST` | `/api/productos/pendientes/descontar` | Descontar estado Pendiente | Operación |

#### Movimientos (`/api/movimientos`)

| Método | Endpoint | Descripción | Tipo |
|--------|----------|-------------|------|
| `GET` | `/api/movimientos` | Listar todos los movimientos | Consulta |
| `GET` | `/api/movimientos/{movimiento_id}` | Obtener movimiento específico | Consulta |
| `POST` | `/api/movimientos` | Crear movimiento | Operación |
| `DELETE` | `/api/movimientos/{movimiento_id}` | Eliminar movimiento | Operación |
| `PUT` | `/api/movimientos/{movimiento_id}` | Actualizar movimiento | Operación |

#### Proveedores (`/api/proveedores`)

| Método | Endpoint | Descripción | Tipo |
|--------|----------|-------------|------|
| `GET` | `/api/proveedores` | Listar proveedores | Consulta |
| `POST` | `/api/proveedores` | Crear proveedor | Operación |
| `DELETE` | `/api/proveedores/{proveedor_id}` | Eliminar proveedor | Operación |
| `PUT` | `/api/proveedores/{proveedor_id}` | Actualizar proveedor | Operación |
| `POST` | `/api/proveedores/solicitudes` | Solicitar piezas (síncrono) | Operación |
| `POST` | `/api/proveedores/solicitudes_async` | Solicitar piezas (asíncrono) | Operación asíncrona |
| `GET` | `/api/proveedores/solicitudes_async/{id}` | Obtener estado solicitud async | Consulta |
| `GET` | `/api/proveedores/solicitudes_async` | Listar solicitudes async | Consulta |
| `POST` | `/api/proveedores/solicitudes_async/reset` | Resetear solicitudes async | Administración |
| `GET` | `/api/proveedores/{proveedor_id}` | Obtener proveedor específico | Consulta |

---

## 3.2 Endpoints Externos que Consumimos

### API Externa de Fabricación (Puerto 8555)
**Consumida por**: API de Inventario
**Archivo**: `app/services/fabricacion/fabricacion_service.py`
**Método HTTP**: `httpx`
**Base URL**: Configurada dinámicamente (ver [Configuración](#configuración-api-externa-de-fabricación))

| Método | Endpoint | Propósito | Usado en |
|--------|----------|-----------|----------|
| `GET` | `/fabricacion/planos/{plano_id}` | Obtener detalles de un plano de fabricación | FabricacionOrchestrator |
| `POST` | `/fabricacion/calculo_piezas` | Calcular piezas necesarias para fabricación | FabricacionOrchestrator |
| `POST` | `/fabricacion/confirmar_fabricacion` | Confirmar inicio de proceso de fabricación | FabricacionOrchestrator |

**Validaciones implementadas**:
- Prevención de URLs malformadas
- Validación de espacios en URLs
- Validación de puertos válidos en rutas
- Clase: `FabricationURLValidator`

---

## 3.3 Flujo de Fabricación

### Flujo: Proceso Completo de Fabricación

```
┌──────────────────┐  POST /api/fabricacion/ordenes  ┌──────────────────────────┐
│  Cliente API     │ ─────────────────────────────> │   API Inventario         │
│  (Externo)       │         (202 Accepted)          │   (FabricationOrchestrator)│
└──────────────────┘                                 └──────────────────────────┘
                                                                │
                      ┌─────────────────────────────────────────┼─────────────────────────────────────┐
                      │                                         │                                     │
                      ▼                                         ▼                                     ▼
        POST /fabricacion/calculo_piezas     POST /fabricacion/confirmar_fabricacion    Redis (Job Queue)
              ┌──────────────────┐                  ┌──────────────────┐                    RQ Worker
              │  API Externa de  │                  │  API Externa de  │
              │   Fabricación    │                  │   Fabricación    │
              └──────────────────┘                  └──────────────────┘
                                                            │
                                          (Proceso asíncrono de fabricación)
                                                            │
                                                            ▼
                               POST /api/fabricacion/webhook/productos_terminados
                                                ┌──────────────────┐
                                                │  API Inventario  │
                                                │    (Webhook)     │
                                                └──────────────────┘
                                                         │
                                                         ▼
                                  POST /api/productos/ingresos (actualizar inventario)
                                                         │
                                                         ▼
                                                 PostgreSQL (inventarios_db)
```

### Flujo: Solicitud de Piezas a Proveedores

```
┌──────────────────┐  POST /api/proveedores/solicitudes_async  ┌──────────────────┐
│  Cliente API     │ ────────────────────────────────────────> │  API Inventario  │
│  (Externo)       │              (202 Accepted)                │                  │
└──────────────────┘                                             └──────────────────┘
                                                                          │
                                                                          ▼
                                                                   Redis (Job Queue)
                                                                      RQ Worker
                                                                          │
                                                                          ▼
                                                        Procesar solicitudes (async)
                                                                          │
                                                                          ▼
                                                           POST /api/piezas (actualizar)
```

---

# ⚙️ CONFIGURACIÓN TÉCNICA

## 4.1 Configuración de URLs

### API de Inventario

**Variables de entorno** (`.env`):

```bash
# Base de datos
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/inventarios_db

# Redis
REDIS_URL=redis://redis:6379/0

# API Externa de Fabricación
FABRICA_BASE_URL=http://host.docker.internal:8555
FABRICA_BASE_URL_FALLBACK=http://localhost:8555
```

#### Configuración: API Externa de Fabricación

**URLs candidatas de fallback** (en orden de prioridad):
1. `FABRICA_BASE_URL` (variable de entorno)
2. Valor almacenado en Redis (clave: `fabricacion:base_url`)
3. `http://host.docker.internal:8555` (Docker default)
4. `http://localhost:8555` (Local fallback)
5. `http://127.0.0.1:8555` (Loopback)

---

### API de Ventas (Backend)

**Variables de entorno** (`.env`):

```bash
# Base de datos
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sales_db?schema=public

# Puerto del servidor
PORT=3000

# API de Inventario
INVENTORY_API_URL=http://localhost:3001
# En Docker: http://inventario-api:3000

# API de Dispatch/Despacho
DISPATCH_API_URL=http://localhost:3002
```

---

## 4.2 Puertos y Servicios

| Servicio | Puerto | Tecnología |
|----------|--------|------------|
| API de Inventario | 3001 | FastAPI (Python) |
| API de Ventas | 3000 | Express.js (Node.js/TypeScript) |
| API de Dispatch | 3002 | (Servicio externo) |
| API Externa de Fabricación | 8555 | FastAPI (Python) |
| PostgreSQL (Inventario) | 5432 | PostgreSQL |
| PostgreSQL (Ventas) | 5432 | PostgreSQL |
| Redis | 6379 | Redis |

---

## 4.3 Bases de Datos

| Base de datos | Propósito | ORM/Driver |
|---------------|-----------|------------|
| `inventarios_db` | Inventario, productos, piezas, fabricación | SQLAlchemy + psycopg |
| `sales_db` | Ventas, personas/clientes | Prisma |

---

## 4.4 Librerías de Comunicación HTTP

### API de Inventario (Python)
- **Librería**: `httpx`
- **Uso**: Llamadas a API Externa de Fabricación
- **Características**: Async/Await, HTTP/2 support
- **Archivo**: `app/services/fabricacion/fabricacion_service.py`

### API de Ventas (Node.js/TypeScript)
- **Librería**: `axios`
- **Uso**: Llamadas a API de Inventario y API de Dispatch
- **Características**: Promises, interceptors, automatic JSON parsing
- **Archivos**:
  - `backend/src/controllers/salesController.ts`
  - `backend/src/services/dispatchService.ts`

---

## 4.5 Seguridad

### Validaciones Implementadas
- **API de Inventario**: `FabricationURLValidator` previene inyección de URLs maliciosas
- **API de Ventas**: Validación con `zod` para esquemas de datos
- **Autenticación**: (Pendiente de documentar si existe)

### Recomendaciones
- ✅ Implementar autenticación y autorización en endpoints críticos
- ✅ Usar HTTPS en producción
- ✅ Implementar rate limiting
- ✅ Validar y sanitizar todos los inputs
- ✅ Implementar circuit breakers para llamadas a APIs externas
- ✅ Implementar timeout en llamadas HTTP
- ✅ Logging y monitoreo de requests

---

## 4.6 Dependencias Principales

### Python (API de Inventario)
```
fastapi==0.115.6
uvicorn
httpx
sqlalchemy==2.0.36
psycopg==3.2.12
redis==5.2.1
rq==1.16.2
```

### Node.js (API de Ventas)
```
express
typescript
@prisma/client
axios
cors
zod
```

---

**Última actualización**: 2025-12-10
**Versión del documento**: 2.0 (Reorganizado por áreas de negocio)
