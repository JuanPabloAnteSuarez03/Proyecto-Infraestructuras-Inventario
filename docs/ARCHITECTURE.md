# Arquitectura del proyecto

## Capas
- `app/api`: Endpoints FastAPI (solo orquestan; validan con Pydantic).
- `app/services`: Lógica de negocio por dominio:
  - `inventario/`: productos, piezas, movimientos.
  - `fabricacion/`: planos/confirmación externa, orquestador de órdenes, acumulación de entregas.
  - `proveedores/`: proveedores y solicitudes async.
- `app/repositories`: Acceso a base de datos (SQLAlchemy).
- `app/domain`: Constantes/planes base sin I/O.
- `app/core`: utilidades transversales (logging, lifecycle).
- `app/tasks.py`: Workers RQ para solicitudes de piezas y consumo de piezas.

## Árbol actual (núcleo)
```
app/
  api/
    inventario_productos_controller.py
    inventario_piezas_controller.py
    proveedores_controller.py
    movimientos_controller.py
    fabricacion_controller.py
  services/
    inventario/ (productos, piezas, movimientos)
    fabricacion/ (fabricacion_service, ordenes, entregas, orchestrator)
    proveedores/ (proveedores, solicitudes)
    __init__.py (reexports)
  repositories/ (CRUD por tabla)
  models/entities.py (SQLAlchemy)
  domain/ (planes y normalizadores)
  core/logging_config.py
  routes.py, __init__.py, database.py
```

## Flujo principal
1) Cliente llama endpoints en `api`.
2) Controllers delegan a `services` (reglas de negocio).
3) Services usan `repositories` para persistencia y `domain` para reglas puras.
4) Workers (`app/tasks.py`) atienden cola RQ para solicitudes de piezas y órdenes (consumo de piezas y espera de webhooks).

## Artefactos externos
- La referencia/mocks de fábrica externa quedaron en `external/` (`fabricacion-api*` y zips) para aislarlos del código de producción.
