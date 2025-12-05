# 📊 Flujos de Inventario

## Introducción

Este documento describe los **flujos de negocio** del sistema de inventario con diagramas de secuencia detallados. Cada flujo muestra cómo interactúan los componentes (API, Workers, Redis, PostgreSQL) para completar una operación.

## Índice de Flujos

1. [Flujo 1: Solicitud de Pieza Asíncrona](#flujo-1-solicitud-de-pieza-asíncrona)
2. [Flujo 2: Orden de Fabricación](#flujo-2-orden-de-fabricación)
3. [Flujo 3: Ingreso de Productos](#flujo-3-ingreso-de-productos)
4. [Flujo 4: Reserva de Stock (VENTAS)](#flujo-4-reserva-de-stock-ventas)
5. [Flujo 5: Despacho de Productos](#flujo-5-despacho-de-productos)
6. [Flujo 6: Transferencia entre Estados](#flujo-6-transferencia-entre-estados)

---

## Flujo 1: Solicitud de Pieza Asíncrona

### Descripción
Cliente solicita piezas a un proveedor de forma asíncrona. La API responde inmediatamente y un worker procesa la solicitud en background.

### Diagrama de Secuencia

```mermaid
sequenceDiagram
    participant C as Cliente
    participant API as API FastAPI
    participant DB as PostgreSQL
    participant R as Redis Queue
    participant W as Worker RQ

    C->>API: POST /api/proveedores/solicitudes_async<br/>{id_pieza: 1, cantidad: 100}
    
    Note over API: Validar request
    API->>DB: INSERT INTO solicitudes_pieza<br/>(estado: "pendiente")
    DB-->>API: Solicitud #5 creada
    
    API->>R: Encolar procesar_solicitud_pieza(5)
    Note over R: Job encolado
    
    API-->>C: 202 Accepted<br/>{id: 5, estado: "pendiente"}<br/>⏱️ ~50ms
    
    Note over W: Worker monitorea cola...
    R-->>W: Job disponible: procesar_solicitud_pieza(5)
    
    W->>DB: UPDATE solicitudes_pieza<br/>SET estado = "en_proceso"<br/>WHERE id = 5
    
    W->>DB: SELECT proveedor WHERE id = ...
    DB-->>W: {tiempo: 5 minutos}
    
    Note over W: Simular pedido<br/>time.sleep(min(5*60, 1))
    
    W->>DB: UPDATE inventario_piezas<br/>SET cantidad = cantidad + 100<br/>WHERE id = 1
    
    W->>DB: UPDATE solicitudes_pieza<br/>SET estado = "completada"<br/>WHERE id = 5
    
    Note over W: Worker termina ✓
    
    Note over C: Cliente consulta estado
    C->>API: GET /api/proveedores/solicitudes_async/5
    API->>DB: SELECT * FROM solicitudes_pieza WHERE id = 5
    DB-->>API: {id: 5, estado: "completada"}
    API-->>C: {id: 5, estado: "completada", ...}
```

### Estados de la Solicitud

```mermaid
stateDiagram-v2
    [*] --> pendiente: API crea solicitud
    pendiente --> en_proceso: Worker inicia
    en_proceso --> completada: Worker termina OK
    en_proceso --> fallida: Worker falla
    completada --> [*]
    fallida --> [*]
```

### Código Clave

**Endpoint (API):**
```python
@router.post("/solicitudes_async", status_code=202)
def solicitar_piezas_async(body, db):
    # 1. Crear solicitud
    solicitud = solicitudes_service.create({
        "id_pieza": body.id_pieza,
        "cantidad": body.cantidad,
        "estado": "pendiente"
    })
    
    # 2. Encolar worker
    queue.enqueue(procesar_solicitud_pieza, solicitud.id)
    
    # 3. Responder inmediatamente
    return {"id": solicitud.id, "estado": "pendiente"}
```

**Worker:**
```python
def procesar_solicitud_pieza(solicitud_id):
    # 1. Cambiar a "en_proceso"
    solicitud.estado = "en_proceso"
    session.commit()
    
    # 2. Simular pedido a proveedor
    tiempo = proveedor.tiempo
    time.sleep(min(tiempo, 1))
    
    # 3. Incrementar inventario
    pieza.cantidad += solicitud.cantidad
    solicitud.estado = "completada"
    session.commit()
```

### Ejemplo de Uso

```bash
# 1. Solicitar piezas
curl -X POST http://localhost:5050/api/proveedores/solicitudes_async \
  -H "Content-Type: application/json" \
  -d '{"id_pieza": 1, "cantidad": 100}'

# Respuesta inmediata:
# {"id": 5, "estado": "pendiente", "tiempo_estimado": 0}

# 2. Consultar estado (después de unos segundos)
curl http://localhost:5050/api/proveedores/solicitudes_async/5

# Respuesta:
# {"id": 5, "id_pieza": 1, "cantidad": 100, "estado": "completada"}
```

---

## Flujo 2: Orden de Fabricación

### Descripción
Cliente crea una orden de fabricación. El sistema calcula piezas necesarias, solicita las faltantes a proveedores, confirma con fábrica externa y encola un worker para consumir piezas.

### Diagrama de Secuencia

```mermaid
sequenceDiagram
    participant C as Cliente
    participant API as API FastAPI
    participant O as Orchestrator
    participant DB as PostgreSQL
    participant R as Redis Queue
    participant W as Worker RQ

    C->>API: POST /api/fabricacion/ordenes<br/>{id_producto: "S1", cantidad: 100}
    
    API->>O: crear_orden("S1", 100)
    
    O->>DB: INSERT INTO ordenes_fabricacion<br/>(estado: "calculando")
    DB-->>O: Orden #25 creada
    
    Note over O: Calcular piezas necesarias
    O->>O: solicitar_plan("S1", 100)
    Note over O: Plan: P1 x 100, P2 x 200, P3 x 150
    
    Note over O: Verificar inventario de piezas
    O->>DB: SELECT cantidad FROM inventario_piezas<br/>WHERE id IN (P1, P2, P3)
    DB-->>O: P1: 50, P2: 300, P3: 100
    
    Note over O: P1 faltante: 50, P3 faltante: 50
    O->>DB: Solicitar P1 (+50) a proveedor
    O->>DB: Solicitar P3 (+50) a proveedor
    
    Note over O: Confirmar con fábrica externa
    O->>O: confirmar_fabricacion_externa("S1", 100)
    Note over O: Fábrica confirma ✓
    
    O->>DB: UPDATE ordenes_fabricacion<br/>SET estado = "confirmado"
    
    O->>R: Encolar procesar_orden_fabricacion(25)
    
    O-->>API: {id: 25, estado: "confirmado", ...}
    API-->>C: 201 Created<br/>{id: 25, estado: "confirmado"}<br/>⏱️ ~200ms
    
    Note over W: Worker procesa en background
    R-->>W: Job: procesar_orden_fabricacion(25)
    
    W->>DB: UPDATE ordenes SET estado = "consumiendo_piezas"
    
    Note over W: Consumir piezas
    W->>DB: UPDATE inventario_piezas<br/>SET cantidad = cantidad - 100 WHERE id = "P1"
    W->>DB: UPDATE inventario_piezas<br/>SET cantidad = cantidad - 200 WHERE id = "P2"
    W->>DB: UPDATE inventario_piezas<br/>SET cantidad = cantidad - 150 WHERE id = "P3"
    
    W->>DB: UPDATE ordenes<br/>SET estado = "esperando_fabricacion"
    
    Note over W: Worker termina<br/>Orden espera productos de fábrica
```

### Estados de la Orden

```mermaid
stateDiagram-v2
    [*] --> calculando: API crea orden
    calculando --> confirmando: Piezas verificadas
    confirmando --> confirmado: Fábrica confirma
    confirmando --> confirmacion_fallida: Fábrica no responde
    confirmado --> consumiendo_piezas: Worker inicia
    consumiendo_piezas --> esperando_fabricacion: Piezas consumidas
    esperando_fabricacion --> completada: Productos llegan (webhook)
    confirmacion_fallida --> fallida: Worker marca fallo
    completada --> [*]
    fallida --> [*]
```

### Código Clave

**Orchestrator:**
```python
def crear_orden(self, codigo, cantidad):
    # 1. Crear orden
    orden = self.ordenes_service.create({
        "id_producto": codigo,
        "cantidad": cantidad,
        "estado": "calculando"
    })
    
    # 2. Calcular piezas
    plan = self.fabricacion_service.solicitar_plan(codigo, cantidad)
    
    # 3. Solicitar piezas faltantes
    for material in plan.materiales:
        if disponible < necesario:
            self.proveedores_service.solicitar_piezas(...)
    
    # 4. Confirmar con fábrica
    confirmacion = self.fabricacion_service.confirmar_fabricacion_externa(...)
    
    if confirmacion["status"] == "ok":
        orden.estado = "confirmado"
        # 5. Encolar worker
        queue.enqueue(procesar_orden_fabricacion, orden.id)
    
    return {"id": orden.id, "estado": orden.estado}
```

**Worker:**
```python
def procesar_orden_fabricacion(orden_id):
    orden = obtener_orden(orden_id)
    
    # 1. Validar estado
    if orden.estado == "confirmado":
        orden.estado = "consumiendo_piezas"
        session.commit()
        
        # 2. Obtener plan
        plan = fabricacion_service.solicitar_plan(orden.id_producto, orden.cantidad)
        
        # 3. Consumir piezas
        for material in plan.materiales:
            pieza.cantidad -= material["cantidad"]
        session.commit()
        
        # 4. Esperar productos
        orden.estado = "esperando_fabricacion"
        session.commit()
```

---

## Flujo 3: Ingreso de Productos

### Descripción
Productos terminados ingresan al inventario (ya sea manualmente o por webhook de fábrica). El sistema incrementa el inventario y completa órdenes pendientes automáticamente.

### Diagrama de Secuencia

```mermaid
sequenceDiagram
    participant F as Fábrica/Usuario
    participant API as API FastAPI
    participant S as ProductosService
    participant DB as PostgreSQL

    F->>API: POST /api/productos/ingresos<br/>{codigo: "S1", cantidad: 100, estado: "Disponible"}
    
    Note over API: Validar código y estado
    
    API->>S: incrementar_stock("S1", 100, "Disponible")
    
    S->>DB: UPDATE inventario_productos<br/>SET cantidad = cantidad + 100<br/>WHERE id_producto = "S1" AND estado = "Disponible"
    
    Note over S: Buscar órdenes pendientes
    S->>DB: SELECT * FROM ordenes_fabricacion<br/>WHERE id_producto = "S1"<br/>AND estado = "esperando_fabricacion"<br/>ORDER BY id ASC
    
    DB-->>S: [Orden #25: cantidad=100, recibido=0]
    
    Note over S: Completar orden #25
    S->>DB: UPDATE ordenes_fabricacion<br/>SET estado = "completada",<br/>cantidad_recibida = 100<br/>WHERE id = 25
    
    Note over S: Log: Orden #25 completada ✓
    
    S-->>API: {mensaje: "Ingreso exitoso", orden_completada: 25}
    API-->>F: 200 OK<br/>{id_producto: "S1", cantidad: 100, ...}
```

### Lógica de Completar Órdenes

```python
def incrementar_stock(codigo, cantidad, estado):
    # 1. Incrementar inventario
    producto.cantidad += cantidad
    
    # 2. Buscar órdenes pendientes
    ordenes = session.query(OrdenFabricacion)\
        .filter_by(id_producto=codigo, estado="esperando_fabricacion")\
        .order_by(OrdenFabricacion.id.asc())\
        .all()
    
    # 3. Completar órdenes
    cantidad_disponible = cantidad
    for orden in ordenes:
        faltante = orden.cantidad - orden.cantidad_recibida
        
        if cantidad_disponible >= faltante:
            # Completar orden completa
            orden.cantidad_recibida = orden.cantidad
            orden.estado = "completada"
            cantidad_disponible -= faltante
            print(f"[INGRESO] ✓ Orden #{orden.id} completada")
        else:
            # Completar parcialmente
            orden.cantidad_recibida += cantidad_disponible
            cantidad_disponible = 0
            break
    
    session.commit()
```

---

## Flujo 4: Reserva de Stock (VENTAS)

### Descripción  
El módulo de VENTAS solicita reservar stock. El sistema verifica disponibilidad y mueve productos de `Disponible` → `Reservado`.

### Diagrama de Secuencia

```mermaid
sequenceDiagram
    participant V as VENTAS
    participant API as API Inventario
    participant S as ProductosService
    participant DB as PostgreSQL

    V->>API: POST /api/productos/reservas<br/>{id_producto: "S1", cantidad: 50}
    
    API->>S: reservar_stock("S1", 50)
    
    Note over S: Verificar stock disponible
    S->>DB: SELECT cantidad FROM inventario_productos<br/>WHERE id_producto = "S1" AND estado = "Disponible"
    DB-->>S: cantidad: 100
    
    alt Stock suficiente (100 >= 50)
        Note over S: Transferir Disponible → Reservado
        S->>DB: UPDATE inventario_productos<br/>SET cantidad = cantidad - 50<br/>WHERE id_producto = "S1" AND estado = "Disponible"
        S->>DB: UPDATE inventario_productos<br/>SET cantidad = cantidad + 50<br/>WHERE id_producto = "S1" AND estado = "Reservado"
        
        S-->>API: {cantidad_confirmada: 50, reservado: true}
        API-->>V: 200 OK<br/>{cantidad_confirmada: 50, cantidad_disponible: 50, reservado: true}
    else Stock insuficiente (< 50)
        Note over S: Solicitar fabricación adicional
        S->>S: solicitar_fabricacion("S1", faltante)
        S-->>API: {cantidad_confirmada: X, fabricado: true, tiempo_estimado: Y}
        API-->>V: 200 OK<br/>{cantidad_confirmada: X, fabricado: true, tiempo_estimado: Y}
    end
```

### Validación de Stock Mínimo

Después de reservar, el sistema verifica si `Disponible` cayó por debajo del umbral (500 unidades):

```python
def _verificar_stock_minimo_async(codigo):
    disponible = obtener_cantidad_disponible(codigo)
    
    if disponible < 500:  # Umbral mínimo
        # Calcular cuánto producir para llegar a 1000
        cantidad_a_producir = max(1000 - disponible, 500)
        
        # Crear orden de fabricación
        crear_orden_fabricacion(codigo, cantidad_a_producir)
```

---

## Flujo 5: Despacho de Productos

### Descripción
VENTAS confirma una venta. El sistema mueve productos de `Reservado` → `A Despacho`.

### Diagrama

```mermaid
sequenceDiagram
    participant V as VENTAS
    participant API as API Inventario
    participant S as ProductosService
    participant DB as PostgreSQL

    V->>API: POST /api/productos/despachos<br/>{id_producto: "S1", cantidad: 50}
    
    API->>S: despachar_stock("S1", 50)
    
    S->>DB: SELECT cantidad FROM inventario_productos<br/>WHERE id_producto = "S1" AND estado = "Reservado"
    DB-->>S: cantidad: 50
    
    Note over S: Transferir Reservado → A Despacho
    S->>DB: UPDATE inventario_productos<br/>SET cantidad = cantidad - 50<br/>WHERE estado = "Reservado"
    S->>DB: UPDATE inventario_productos<br/>SET cantidad = cantidad + 50<br/>WHERE estado = "A Despacho"
    
    S-->>API: {cantidad_confirmada: 50, despachado: true}
    API-->>V: 200 OK<br/>{cantidad_confirmada: 50, despachado: true}
```

---

## Flujo 6: Transferencia entre Estados

### Descripción
Transferencia manual de stock entre cualquier par de estados.

### Diagrama

```mermaid
sequenceDiagram
    participant U as Usuario
    participant API as API
    participant S as ProductosService
    participant DB as PostgreSQL

    U->>API: POST /api/productos/transferencias<br/>{id_producto: "S1", estado_origen: "Disponible",<br/>estado_destino: "Reservado", cantidad: 30}
    
    API->>S: transferir_stock("S1", "Disponible", "Reservado", 30)
    
    Note over S: Validar stock suficiente
    S->>DB: SELECT cantidad FROM inventario_productos<br/>WHERE id_producto = "S1" AND estado = "Disponible"
    DB-->>S: cantidad: 100
    
    alt Stock suficiente (100 >= 30)
        S->>DB: UPDATE SET cantidad = cantidad - 30<br/>WHERE estado = "Disponible"
        S->>DB: UPDATE SET cantidad = cantidad + 30<br/>WHERE estado = "Reservado"
        S-->>API: {mensaje: "Transferencia exitosa"}
        API-->>U: 200 OK
    else Stock insuficiente
        S-->>API: ValueError("Stock insuficiente")
        API-->>U: 400 Bad Request<br/>{detail: "Stock insuficiente"}
    end
```

---

## Resumen de Flujos

| Flujo | Tipo | Tiempo de Respuesta | Procesamiento |
|-------|------|---------------------|---------------|
| Solicitud de pieza async | Asíncrono | ~50ms | Worker background |
| Orden de fabricación | Asíncrono | ~200ms | Worker background |
| Ingreso de productos | Síncrono | ~100ms | Inmediato |
| Reserva de stock | Síncrono | ~50ms | Inmediato (+ async si fabrica) |
| Despacho | Síncrono | ~50ms | Inmediato |
| Transferencia | Síncrono | ~50ms | Inmediato |

## Convenciones de Estados

### Productos
- **Disponible**: Stock listo para vender
- **Reservado**: Stock apartado para venta (temporal)
- **A Despacho**: Stock confirmado para envío

### Solicitudes de Pieza
- **pendiente**: Creada, esperando worker
- **en_proceso**: Worker procesando
- **completada**: Pieza recibida ✓
- **fallida**: Error en procesamiento ✗

### Órdenes de Fabricación
- **calculando**: Calculando piezas necesarias
- **confirmando**: Contactando fábrica
- **confirmado**: Fábrica aceptó orden
- **consumiendo_piezas**: Worker consumiendo materiales
- **esperando_fabricacion**: Esperando productos de fábrica
- **completada**: Productos recibidos ✓
- **fallida**: Error ✗

## Siguientes Pasos

Ahora que conoces los flujos:

1. **Aprende a desarrollar:** Lee [05_GUIA_DESARROLLO.md](05_GUIA_DESARROLLO.md)
2. **Prueba los flujos:** Lee [TESTING.md](TESTING.md)
