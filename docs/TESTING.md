# Guía de Pruebas - API de Fabricación

## Información de la Fábrica Externa

**URL Base:** `http://ec2-98-93-67-35.compute-1.amazonaws.com:8555`

**Documentación Swagger:** http://ec2-98-93-67-35.compute-1.amazonaws.com:8555/docs

### Planos Disponibles

| Código | Plano ID | Nombre | Tiempo Fabricación |
|--------|----------|--------|-------------------|
| S1 | 1 | Sierra Clásica | 1 minuto |
| S2 | 2 | Sierra Diamantada | 1 minuto |

### Piezas Requeridas (S1)

Para fabricar 100 unidades de S1 se necesitan:
- P1: 100 unidades
- P2: 100 unidades
- P3: 100 unidades
- P4: 100 unidades

**Nota:** S2 actualmente no tiene piezas asociadas en la base de datos de la fábrica externa.

## Comandos CLI Disponibles

### 1. Probar conexión con la fábrica
```bash
sudo docker compose exec api python -m app.cli test-fabrica
```

### 2. Resetear inventario a cero
```bash
sudo docker compose exec api python -m app.cli reset-inventory
```

### 3. Crear base de datos
```bash
sudo docker compose exec api python -m app.cli create-db
```

### 4. Cargar datos de ejemplo
```bash
sudo docker compose exec api python -m app.cli seed-db
```

## Scripts de Prueba

### Script Python Independiente

Ejecutar pruebas completas desde fuera de Docker:

```bash
python test_fabrica.py
```

Este script prueba:
- Conexión con la fábrica externa
- Planos de fabricación
- Cálculo de piezas
- Conexión con tu API local
- Estado de integración

## Endpoints de la API Local

### Fabricación

#### Obtener plan de fabricación
```bash
curl "http://localhost:5050/api/fabricacion/plan/S1?cantidad=100"
```

#### Crear orden de fabricación
```bash
curl -X POST "http://localhost:5050/api/fabricacion/ordenes" \
  -H "Content-Type: application/json" \
  -d '{"id_producto": "S1", "cantidad": 100}'
```

#### Listar órdenes
```bash
curl "http://localhost:5050/api/fabricacion/ordenes"
```

#### Ver detalle de orden
```bash
curl "http://localhost:5050/api/fabricacion/ordenes/1"
```

#### Verificar estado de fábrica externa
```bash
curl "http://localhost:5050/api/fabricacion/external/status"
```

### Inventario

#### Listar productos
```bash
curl "http://localhost:5050/api/inventario/productos"
```

#### Listar piezas
```bash
curl "http://localhost:5050/api/inventario/piezas"
```

### Proveedores

#### Listar proveedores
```bash
curl "http://localhost:5050/api/proveedores"
```

#### Solicitar piezas
```bash
curl -X POST "http://localhost:5050/api/proveedores/solicitar" \
  -H "Content-Type: application/json" \
  -d '{"id_pieza": "P1", "cantidad": 100}'
```

## Webhook para Fábrica Externa

La fábrica externa debe enviar notificaciones de productos terminados a:

```
POST http://TU_IP_PUBLICA:5050/api/fabricacion/webhook/productos_terminados
```

**Body:**
```json
{
  "codigo": "S1",
  "cantidad": 1500,
  "estado": "Disponible"
}
```

## Flujo Completo de Fabricación

1. **Verificar inventario actual**
   ```bash
   curl "http://localhost:5050/api/inventario/productos"
   ```

2. **Resetear inventario (opcional, para pruebas)**
   ```bash
   sudo docker compose exec api python -m app.cli reset-inventory
   ```

3. **Obtener plan de fabricación**
   ```bash
   curl "http://localhost:5050/api/fabricacion/plan/S1?cantidad=100"
   ```

4. **Crear orden de fabricación**
   ```bash
   curl -X POST "http://localhost:5050/api/fabricacion/ordenes" \
     -H "Content-Type: application/json" \
     -d '{"id_producto": "S1", "cantidad": 100}'
   ```

5. **Verificar estado de la orden**
   ```bash
   curl "http://localhost:5050/api/fabricacion/ordenes/1"
   ```

6. **Esperar webhook de fábrica externa**
   - La fábrica enviará productos terminados al webhook
   - La orden se marcará como completada
   - El inventario se actualizará automáticamente

## Configuración del Webhook

Para que la fábrica pueda enviar el webhook, necesitas:

1. **Obtener tu IP pública:**
   ```bash
   curl ifconfig.me
   ```

2. **Actualizar .env:**
   ```
   WEBHOOK_CALLBACK_URL=http://TU_IP_PUBLICA:5050/api/fabricacion/webhook/productos_terminados
   ```

3. **Reiniciar contenedores:**
   ```bash
   sudo docker compose restart
   ```

## Troubleshooting

### La fábrica no responde
```bash
# Verificar que la URL esté configurada
cat .env | grep FABRICA_BASE_URL

# Probar conexión
sudo docker compose exec api python -m app.cli test-fabrica
```

### El webhook no funciona
```bash
# Verificar que el puerto 5050 esté abierto
sudo ufw status
sudo ufw allow 5050

# Verificar logs
sudo docker compose logs -f api
```

### Base de datos vacía
```bash
# Cargar datos de ejemplo
sudo docker compose exec api python -m app.cli seed-db
```

## Documentación Interactiva

- **API Local:** http://localhost:5050/docs
- **Fábrica Externa:** http://ec2-98-93-67-35.compute-1.amazonaws.com:8555/docs
