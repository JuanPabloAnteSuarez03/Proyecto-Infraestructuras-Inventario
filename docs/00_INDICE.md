# 📚 Documentación del Sistema de Inventario

Bienvenido a la documentación del **Sistema de Inventario con Procesamiento Asíncrono**. Este sistema utiliza **FastAPI**, **Redis**, **RQ (Redis Queue)** y **PostgreSQL** para gestionar inventarios de productos y piezas con procesamiento en background.

## 🗺️ Mapa de Documentación

### Para Empezar
1. **[README.md](README.md)** - Introducción rápida y quick start
2. **[01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md)** - Visión completa del sistema

### Conceptos Clave ⭐
3. **[02_SISTEMA_COLAS.md](02_SISTEMA_COLAS.md)** - Redis + RQ: Cómo funciona el encolado
4. **[03_PARALELISMO_CONCURRENCIA.md](03_PARALELISMO_CONCURRENCIA.md)** - API + Workers concurrentes
5. **[04_FLUJOS_INVENTARIO.md](04_FLUJOS_INVENTARIO.md)** - Diagramas de flujos de negocio

### Para Desarrolladores
6. **[05_GUIA_DESARROLLO.md](05_GUIA_DESARROLLO.md)** - Cómo extender el sistema
7. **[TESTING.md](TESTING.md)** - Pruebas automatizadas

## 🎯 Guías de Lectura por Perfil

### 👨‍💻 Nuevo Desarrollador
> "Quiero entender cómo funciona el sistema"

1. Lee **README.md** para entender qué hace el sistema
2. Lee **01_ARQUITECTURA_GENERAL.md** para ver la estructura completa
3. Lee **02_SISTEMA_COLAS.md** para entender el procesamiento asíncrono
4. Lee **03_PARALELISMO_CONCURRENCIA.md** para entender la concurrencia
5. Sigue **05_GUIA_DESARROLLO.md** para hacer tu primera contribución

### 🏗️ Arquitecto de Software
> "Necesito entender decisiones de diseño"

1. **01_ARQUITECTURA_GENERAL.md** - Patrones y capas
2. **02_SISTEMA_COLAS.md** - Por qué usar colas, escalabilidad
3. **03_PARALELISMO_CONCURRENCIA.md** - Gestión de estado compartido

### 📊 Product Manager / Analista
> "Quiero entender los flujos de negocio"

1. **README.md** - Funcionalidades principales
2. **04_FLUJOS_INVENTARIO.md** - Diagramas de flujos detallados

### 🔧 DevOps / SRE
> "Necesito deployar y monitorear"

1. **README.md** - Configuración de Docker Compose
2. **02_SISTEMA_COLAS.md** - Monitoreo de colas y workers
3. **TESTING.md** - Pruebas de integración

## 🔑 Conceptos Clave del Sistema

### Sistema de Colas (Redis + RQ)
El sistema utiliza **colas de trabajo** para procesar tareas lentas en background:
- ✅ API responde rápido (no bloquea)
- ✅ Workers procesan tareas asíncronamente
- ✅ Escalable horizontalmente

**Ejemplo:** Solicitar piezas a proveedor
```
Usuario → API → Encolar trabajo → Respuesta inmediata
                     ↓
                 Worker → Simula pedido → Actualiza inventario
```

### Paralelismo y Concurrencia
- **API (FastAPI)**: Maneja múltiples requests simultáneos
- **Workers (RQ)**: Procesan trabajos en paralelo
- **PostgreSQL**: Fuente de verdad compartida

### Arquitectura por Capas
```
API Layer       → Controllers (app/api/)
Service Layer   → Business Logic (app/services/)
Repository Layer → Data Access (app/repositories/)
Domain Layer    → Core Logic (app/domain/)
```

## 📦 Componentes del Sistema

| Componente | Tecnología | Puerto | Descripción |
|------------|------------|--------|-------------|
| **API** | FastAPI + Uvicorn | 5050 | Endpoints REST |
| **Worker** | RQ | - | Procesamiento asíncrono |
| **Redis** | Redis 7 | 6379 | Cola de mensajes |
| **DB** | PostgreSQL 15 | 5434 (HOST_POSTGRES_PORT) | Base de datos |

## 🚀 Quick Start

```bash
# 1. Levantar servicios
# Si tienes otro Postgres local en el mismo puerto, cambia HOST_POSTGRES_PORT en .env
docker compose up --build

# 2. Crear tablas
docker compose exec api python -m app.cli create-db

# 3. Cargar datos de ejemplo
docker compose exec api python -m app.cli seed-db

# 4. Probar API
curl http://localhost:5050/health
curl http://localhost:5050/api/productos
```

## 📖 Estructura de Documentos

### 01_ARQUITECTURA_GENERAL.md
- Diagrama de arquitectura completa
- Componentes y responsabilidades
- Patrones de diseño
- Flujo de datos

### 02_SISTEMA_COLAS.md
- ¿Qué es RQ y por qué usarlo?
- Arquitectura de colas (productor/consumidor)
- Workers en detalle
- Ejemplos prácticos
- Monitoreo

### 03_PARALELISMO_CONCURRENCIA.md
- Diferencia paralelismo vs concurrencia
- API + Workers ejecutando en paralelo
- Gestión de estado compartido
- Escalabilidad horizontal

### 04_FLUJOS_INVENTARIO.md
- Flujo de solicitud de pieza asíncrona
- Flujo de orden de fabricación
- Flujo de ingreso de productos
- Flujo de reservas/despachos (ventas)

### 05_GUIA_DESARROLLO.md
- Cómo agregar un nuevo worker
- Cómo agregar un endpoint asíncrono
- Cómo testear workers
- Patrones recomendados

## 🔍 Búsqueda Rápida

**¿Cómo funciona el encolado?** → [02_SISTEMA_COLAS.md](02_SISTEMA_COLAS.md)

**¿Cómo escala el sistema?** → [03_PARALELISMO_CONCURRENCIA.md](03_PARALELISMO_CONCURRENCIA.md)

**¿Cómo fluyen las órdenes?** → [04_FLUJOS_INVENTARIO.md](04_FLUJOS_INVENTARIO.md)

**¿Cómo agrego funcionalidad?** → [05_GUIA_DESARROLLO.md](05_GUIA_DESARROLLO.md)

**¿Cómo pruebo el sistema?** → [TESTING.md](TESTING.md)

## 🎓 Recursos Adicionales

- **Código fuente**: `app/` (comentado y documentado)
- **Configuración**: `.env.example`, `docker-compose.yml`
- **Tests**: `tests/`

## 💡 Filosofía del Sistema

Este sistema fue diseñado siguiendo principios de:
- ✅ **Separación de responsabilidades**: Capas bien definidas
- ✅ **Procesamiento asíncrono**: Tareas lentas no bloquean la API
- ✅ **Escalabilidad**: Workers y API pueden escalar independientemente
- ✅ **Mantenibilidad**: Código organizado por dominio
- ✅ **Testabilidad**: Servicios inyectables y mockeables

---

**¿Nuevo en el proyecto?** Comienza por **[README.md](README.md)** y luego lee **[01_ARQUITECTURA_GENERAL.md](01_ARQUITECTURA_GENERAL.md)**

**¿Listo para codear?** Ve directamente a **[05_GUIA_DESARROLLO.md](05_GUIA_DESARROLLO.md)**
