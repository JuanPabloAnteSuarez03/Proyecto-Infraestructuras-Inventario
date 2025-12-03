# Microservicio de Inventarios

Microservicio REST construido con FastAPI. Expone APIs JSON para gestionar inventarios de productos, piezas, proveedores y movimientos logísticos. La persistencia se realiza en PostgreSQL y toda la pila (API + BD) se orquesta con Docker Compose.

## Stack principal
- Python 3.11 + FastAPI
- Flask-SQLAlchemy / Marshmallow para modelos y serialización JSON
- PostgreSQL 15
- Docker y docker-compose como entorno de ejecución

## Estructura del proyecto
```
app/
├── controllers/        # Routers FastAPI
├── models/             # Modelos SQLAlchemy que representan las tablas
├── repositories/       # Acceso a datos encapsulado por entidad
├── schemas/            # Esquemas Marshmallow para validar y serializar JSON
├── services/           # Reglas de negocio
├── data/seed           # Archivos JSON de carga inicial
├── cli.py              # Comandos personalizados (create-db, seed-db)
├── config.py           # Configuración por entorno
└── routes.py           # Registro central de rutas
```

## Puesta en marcha
1. Copie el archivo de variables de entorno:
   ```bash
   cp .env.example .env
   ```
2. Levante la pila completa:
   ```bash
   docker compose up --build
   ```
3. Dentro del contenedor `api`, cree las tablas y cargue datos de ejemplo (JSON en `app/data/seed`):
   ```bash
   docker compose exec api python -c "from app import create_app; from app.extensions import db; create_app(); db.create_all()"
   docker compose exec api python -c "from app import create_app; from app.services.seed_service import load_seed_data; create_app(); load_seed_data()"
   ```
4. La API quedará disponible en `http://localhost:5000`.
   - La base de datos PostgreSQL queda expuesta en `localhost:5433` (útil si deseas conectarte con un cliente externo).

## Endpoints disponibles
Todos los recursos siguen el prefijo `/api` y aceptan/retornan JSON.

| Recurso | GET colección | GET por id | POST | PUT | DELETE |
|---------|---------------|------------|------|-----|--------|
| Inventario de productos | `GET /api/productos` (todos los estados) / `GET /api/productos/<codigo>` (estados del producto) / `GET /api/productos/<codigo>/<estado>` (estado puntual) | Ver descripción | `POST /api/productos` (solo combinaciones válidas S1/S2 + estado) / `POST /api/productos/transferencias` para mover cantidades entre estados / `POST /api/productos/reservas` para reservar stock desde VENTAS / `POST /api/productos/despachos` para confirmar despacho / `POST /api/productos/ingresos` para sumar stock a un estado (`Disponible` por defecto) | `PUT /api/productos/<codigo>/<estado>` | `DELETE /api/productos/<codigo>/<estado>` |
| Inventario de piezas    | `GET /api/piezas`    | `GET /api/piezas/<idPieza>`       | `POST /api/piezas`    | `PUT /api/piezas/<idPieza>`    | `DELETE /api/piezas/<idPieza>` |
| Proveedores             | `GET /api/proveedores` | `GET /api/proveedores/<idProveedor>` | `POST /api/proveedores` | `PUT /api/proveedores/<idProveedor>` | `DELETE /api/proveedores/<idProveedor>` |
| Movimientos             | `GET /api/movimientos` | `GET /api/movimientos/<idMovimiento>` | `POST /api/movimientos` | `PUT /api/movimientos/<idMovimiento>` | `DELETE /api/movimientos/<idMovimiento>` |
| Fábrica / Producción    | `GET /api/fabricacion/plan/<codigo>?cantidad=100` | - | `POST /api/fabricacion/producciones` para producir lotes usando piezas internas / `POST /api/fabricacion/calcular_piezas` para obtener el requerimiento de piezas | - | - |
| Documentación API       | - | - | UI en `/docs` (OpenAPI `/openapi.json`) | - | - |
| Proveedores ↔ Fábrica   | - | - | `POST /api/proveedores/solicitudes` para reabastecer una pieza (`id_pieza`, `cantidad`) | - | - |

### Inventarios gestionados
- **Inventario de productos terminados**: contiene los estados `Disponible`, `Reservado` y `A Despacho` por cada código (`S1`, `S2`). VENTAS consume `reservas`/`despachos`, DESPACHO confirma entregas y FÁBRICA agrega stock terminado (ya sea de forma automática cuando se cruza el umbral de 500 unidades o manualmente mediante `POST /api/fabricacion/producciones`).
- **Inventario de piezas**: almacena los insumos que necesita FÁBRICA para ensamblar los productos. Cada pieza está ligada a un proveedor, lo que permite estimar tiempos de reabastecimiento cuando se requiere producir. El endpoint `GET /api/fabricacion/plan/<codigo>` devuelve la lista de piezas que se consumirían junto con el stock disponible por pieza.
  - Se incluyen por defecto seis piezas (`P1` … `P6`), cada una vinculada a un proveedor (`Prov1` … `Prov6`). Esto permite simular todo el flujo de abastecimiento desde la semilla inicial.

### Ejemplos de carga útil
`POST /api/productos/ingresos` (el campo `estado` es opcional, por defecto `Disponible`)
```json
{
  "id_producto": "S1",
  "cantidad": 250
}
```

`POST /api/productos/transferencias`
```json
{
  "id_producto": "S1",
  "estado_origen": "Disponible",
  "estado_destino": "Reservado",
  "cantidad": 50
}
```

`POST /api/fabricacion/calcular_piezas`
```json
{
  "codigo": "S1",
  "cantidad": 120
}
```

`POST /api/movimientos`
```json
{
  "id_movimiento": 5,
  "id_objeto": 2,
  "tipo_objeto": "pieza",
  "cantidad": 12,
  "direccion": "entrada"
}
```

## Flujo de inventario de productos
- Solo existen dos códigos (`S1` y `S2`) y tres estados posibles por código (`Reservado`, `A Despacho`, `Disponible`). La tabla `inventario_productos` contiene un registro por combinación código-estado.
- Las cantidades se ajustan moviendo stock entre estados mediante `POST /api/productos/transferencias`. Se debe indicar `id_producto`, `estado_origen`, `estado_destino` y `cantidad` (entero positivo). El servicio valida que exista stock suficiente en el origen antes de concretar la transferencia.
- Si necesitas corregir manualmente un estado específico puedes usar `PUT /api/productos/<codigo>/<estado>` con `{"cantidad": X}`.

### Evento VENTAS → INVENTARIO (reservas)
Cuando el microservicio de VENTAS necesita confirmar disponibilidad:
1. Envía `POST /api/productos/reservas` con `{"id_producto": "S1", "cantidad": 15}`.
2. INVENTARIO intenta mover desde `Disponible` hacia `Reservado` la cantidad solicitada (operación temporal que prepara la siguiente etapa del flujo).
3. La respuesta es:
   ```json
   {
     "id_producto": "S1",
     "cantidad_solicitada": 15,
     "cantidad_confirmada": 15,
     "cantidad_pendiente": 0,
     "cantidad_disponible": 85,
     "tiempo_estimado": 0,
     "estado_ingreso": "Reservado",
     "fabricado": false,
      "reservado": true
   }
   ```
   - `estado_ingreso` indica el estado al que se movieron los productos (`Reservado` si salieron del stock disponible, `A Despacho` si se fabricaron específicamente para el pedido). 
   - `fabricado: true` aparece cuando INVENTARIO tuvo que coordinar con FÁBRICA porque no había disponibilidad inmediata; en ese caso la respuesta mostrará `estado_ingreso: "A Despacho"`.

### Evento VENTAS → INVENTARIO (despachos)
Cuando el cliente confirma la compra:
1. VENTAS envía `POST /api/productos/despachos` con `{"id_producto": "S1", "cantidad": 10}`.
2. INVENTARIO mueve la cantidad desde `Reservado` hacia `A Despacho` (stock listo para salir).
3. La respuesta es:
   ```json
   {
     "id_producto": "S1",
     "cantidad_solicitada": 10,
     "cantidad_confirmada": 10,
     "cantidad_pendiente": 0,
     "cantidad_disponible": 80,
     "tiempo_estimado": 0,
     "estado_ingreso": "A Despacho",
     "despachado": true
   }
   ```
   - `despachado: true` confirma que el traslado a `A Despacho` fue exitoso.
   - Si había menos unidades reservadas, INVENTARIO solicita fabricación adicional al microservicio de FÁBRICA. El lote resultante ingresa directamente como `A Despacho`, y `tiempo_estimado` refleja la suma entre el reabastecimiento de piezas y el tiempo de producción.

### Evento INVENTARIO ↔ FÁBRICA
Para evitar que el stock disponible caiga por debajo de los umbrales operativos, INVENTARIO monitorea `Disponible` y se coordina con FÁBRICA y PROVEEDORES:
1. Si el estado `Disponible` de un producto baja de 500 unidades, se solicita automáticamente a FÁBRICA la producción de lotes de 500 unidades hasta alcanzar al menos 1000.
2. FÁBRICA responde con el plan de piezas y el tiempo de producción. INVENTARIO verifica la existencia de las piezas (`inventario_piezas`). Si faltan, se solicitan a PROVEEDORES (tomando el tiempo de entrega registrado).
3. Una vez aseguradas las piezas, se descuentan del inventario de materiales, FÁBRICA produce y se incrementa el estado `Disponible`.
4. Cuando la fabricación se realiza por solicitud directa de VENTAS (por falta de stock o reserva), los productos ingresan como `A Despacho` para distinguirlos de los lotes producidos para reabastecimiento general. El tiempo total estimado (`tiempo_estimado`) que aparece en las respuestas de reservas/despachos incorpora la suma del reabastecimiento de piezas más el tiempo de producción, permitiendo a VENTAS anticipar promesas de entrega incluso cuando inicialmente no había stock suficiente.

- **Planificación manual**: usando `GET /api/fabricacion/plan/<codigo>?cantidad=100`, FÁBRICA puede consultar qué piezas requiere y cuánto tiempo tomará producir un lote. 
- **Producción manual**: `POST /api/fabricacion/producciones` permite registrar un lote producido (por defecto ingresa como Disponible, pero las solicitudes derivadas de VENTAS diferencian automáticamente el estado final).

## Variables de entorno principales
- `DATABASE_URL`: Cadena de conexión SQLAlchemy usada por Flask.
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: Credenciales del contenedor PostgreSQL.
- `FLASK_ENV`: Selecciona la configuración (`development`, `production`, `testing`).
- `FABRICA_BASE_URL`: (opcional) URL base del servicio de Fábrica para consultar `GET /fabricacion/planos/{plano_id}`. Si se define, el tiempo de fabricación se tomará de ese endpoint (mapping por defecto: S1→1, S2→2); si no responde, se usa el plan local.

## Comandos útiles
```bash
# Levantar servicios
docker compose up --build
# Ejecutar pruebas de salud
docker compose exec api curl http://localhost:5000/health
# Reconstruir base de datos (ojo: elimina datos)
docker compose down -v && docker compose up --build
```

## Pruebas automatizadas
Para ejecutar la batería de pruebas (usa la configuración `testing` con SQLite en memoria):
```bash
pip install -r requirements-dev.txt
pytest
```

## Documentación interactiva
- UI: `http://localhost:5000/docs` (o la IP de Tailscale si accedes de forma remota).
- Especificación JSON: `http://localhost:5000/openapi.json`.

Con esto tienes un microservicio listo para extender lógica de negocio, agregar validaciones avanzadas o nuevos endpoints (PUT/PATCH) manteniendo la separación MVC.
