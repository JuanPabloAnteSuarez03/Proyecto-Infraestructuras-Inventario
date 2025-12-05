# 🎯 SOLUCIÓN DEFINITIVA - Webhook Fabricación

## 📢 DESCUBRIMIENTO CRÍTICO

Después de analizar el código fuente de `fabricacion-api`, descubrimos que:

**✅ Los webhooks SÍ ESTÁN IMPLEMENTADOS**
**❌ Pero están configurados con la IP INCORRECTA**

## 🔍 Análisis del Código

### 1. Worker de Fabricación (fabricacion-api)

**Archivo:** `fabricacion-api/app/utils/fabricacion_workers.py` líneas 12-28

```python
def worker_fabricacion(codigo:str, cantidad: int):
    """
    Worker que simula el tiempo de fabricación y envía webhook al terminar
    """
    url = API_PATH_INVENTARIO  # ← Variable de entorno
    client = httpx.Client()

    # Simular fabricación (1/24 segundo por unidad)
    for i in range(0, cantidad):
        time.sleep(1/24)

    # WEBHOOK: Enviar productos terminados
    data = {"codigo": codigo, "cantidad": cantidad}

    try:
        response = client.post(url, json=data)  # ← AQUÍ ENVÍA EL WEBHOOK
        print(response.status_code)
    except Exception as e:
        print(f"[ERROR] Falló actualización inventario: {e}")
```

### 2. Configuración (fabricacion-api)

**Archivo:** `fabricacion-api/app/core/config.py` línea 13

```python
# Variable que controla a dónde se envían los webhooks
API_PATH_INVENTARIO = os.getenv("API_PATH_INVENTARIO", "localhost")
```

### 3. Docker Compose (fabricacion-api)

**Archivo:** `fabricacion-api/compose.yaml` línea 31

```yaml
api:
  environment:
    API_PATH_INVENTARIO: http://100.100.74.70:5050/api/productos/ingresos
    #                          ^^^^^^^^^^^^^^
    #                          IP INCORRECTA ❌
```

### 4. Endpoint Receptor (tu servidor de inventario)

**Archivo:** `app/api/inventario_productos_controller.py` líneas 97-169

```python
@router.post("/ingresos")
def incrementar_producto(body: IngresoProducto, db: Session = Depends(get_db)):
    """
    Endpoint que recibe productos terminados de la fábrica
    """
    codigo = data["id_producto"]
    cantidad = data["cantidad"]
    estado = data.get("estado", "Disponible")

    # 1. Incrementar inventario
    producto = service.incrementar(
        producto_id=codigo,
        estado=estado,
        cantidad=cantidad,
    )

    # 2. Completar órdenes pendientes
    orden = db.query(OrdenFabricacion).filter(
        OrdenFabricacion.id_producto == codigo.upper(),
        OrdenFabricacion.estado == "esperando_fabricacion"
    ).first()

    if orden and cantidad >= orden.cantidad:
        orden.estado = "completada"
        db.commit()
```

## 🛠️ SOLUCIÓN PASO A PASO

### Paso 1: Determinar la IP Correcta

Tienes varias opciones dependiendo de tu infraestructura:

#### Opción A: Ambos servicios en Tailscale ✅ RECOMENDADO

Si ambos servidores están en tu red Tailscale:

```bash
# En el servidor de inventario, obtener IP Tailscale
ip addr show tailscale0
# O ver en panel de Tailscale: https://login.tailscale.com/admin/machines

# IP Tailscale conocida: 100.70.143.89
```

**Ventajas:**
- ✅ Conexión encriptada automática
- ✅ No necesitas abrir puertos al público
- ✅ Funciona a través de NAT/firewalls
- ✅ IP relativamente estable

#### Opción B: Ambos en la misma VPC de AWS

Si ambos están en AWS EC2 en la misma VPC:

```bash
# Usar IP privada de VPC (ejemplo: 172.31.x.x)
# En el servidor de inventario:
hostname -I
```

**Ventajas:**
- ✅ Latencia bajísima
- ✅ Sin costos de transferencia de datos
- ✅ Seguro (red privada)

#### Opción C: IP Pública

Si tu servidor de inventario tiene IP pública:

```bash
# En el servidor de inventario:
curl ifconfig.me
# Tu IP pública: 186.27.169.195
```

**Requisitos:**
- ⚠️ Debes abrir puerto 5050 en el firewall
- ⚠️ Configurar iptables/ufw/security group

### Paso 2: Actualizar fabricacion-api en AWS

```bash
# 1. Conectar al servidor AWS donde corre fabricacion-api
ssh usuario@ec2-98-93-67-35.compute-1.amazonaws.com

# 2. Ir al directorio
cd fabricacion-api

# 3. Editar compose.yaml
nano compose.yaml  # o vim compose.yaml

# 4. Cambiar línea 31:
# ANTES:
API_PATH_INVENTARIO: http://100.100.74.70:5050/api/productos/ingresos

# DESPUÉS (elegir según tu caso):
# Si usas Tailscale:
API_PATH_INVENTARIO: http://100.70.143.89:5050/api/productos/ingresos

# Si usas VPC privada AWS:
API_PATH_INVENTARIO: http://172.31.X.X:5050/api/productos/ingresos

# Si usas IP pública:
API_PATH_INVENTARIO: http://186.27.169.195:5050/api/productos/ingresos

# 5. Guardar y salir (Ctrl+X, Y, Enter en nano)
```

### Paso 3: Reiniciar Servicio de Fábrica

```bash
# En el servidor AWS (fabricacion-api)
docker compose restart api

# Verificar que reinició correctamente
docker compose ps
docker compose logs -f api
```

### Paso 4: Probar el Flujo Completo

```bash
# En tu servidor de inventario

# 1. Resetear inventario para ver cambios claros
sudo docker compose exec api python -m app.cli reset-inventory

# 2. Crear orden de fabricación
curl -X POST http://localhost:5050/api/fabricacion/ordenes \
  -H "Content-Type: application/json" \
  -d '{"id_producto": "S1", "cantidad": 50}'

# Deberías ver respuesta con estado "confirmado"

# 3. Esperar 5-10 segundos (fabricación simulada)
sleep 10

# 4. Verificar que la orden se completó AUTOMÁTICAMENTE
curl -s http://localhost:5050/api/fabricacion/ordenes | \
  python -m json.tool | grep -A8 '"estado": "completada"'

# 5. Verificar que el inventario se actualizó
curl -s http://localhost:5050/api/productos | \
  python -m json.tool | grep -A3 '"id_producto": "S1"'
```

### Paso 5: Monitorear Logs

Terminal 1 (servidor inventario):
```bash
sudo docker compose logs -f api | grep -E "(WEBHOOK|INGRESO)"
```

Terminal 2 (servidor fabricacion-api):
```bash
docker compose logs -f api | grep -i "inventario"
```

## 🎭 Endpoints Equivalentes

Tu servidor de inventario tiene **DOS endpoints** que hacen lo mismo:

### Endpoint 1: `/api/productos/ingresos` (PRINCIPAL)
- Ubicación: `app/api/inventario_productos_controller.py:97`
- **Este es el que usa la fábrica** (según compose.yaml)
- ✅ Incrementa inventario
- ✅ Completa órdenes
- ✅ Maneja entregas parciales

### Endpoint 2: `/api/fabricacion/webhook/productos_terminados` (ALTERNATIVO)
- Ubicación: `app/api/fabricacion_controller.py:295`
- Funcionalidad idéntica al anterior
- Se creó para pruebas/desarrollo

**Puedes usar cualquiera de los dos**, pero la fábrica está configurada para usar `/api/productos/ingresos`.

## 🔍 Debug y Troubleshooting

### Verificar que el webhook llega

```bash
# En servidor inventario, ver todos los requests que llegan
sudo docker compose logs -f api | grep "POST /api/productos/ingresos"
```

### Probar manualmente el webhook

```bash
# Simular que la fábrica envía productos terminados
curl -X POST http://localhost:5050/api/productos/ingresos \
  -H "Content-Type: application/json" \
  -d '{"codigo": "S1", "cantidad": 100, "estado": "Disponible"}'
```

### Verificar conectividad desde AWS

```bash
# Desde el servidor AWS (fabricacion-api)
# Probar si puede alcanzar tu servidor de inventario

# Opción Tailscale:
curl -v http://100.70.143.89:5050/health

# Opción IP pública:
curl -v http://186.27.169.195:5050/health
```

## 📊 Formato del Webhook

**Payload enviado por la fábrica:**
```json
{
  "codigo": "S1",
  "cantidad": 50
}
```

**Payload esperado por tu API:**
```json
{
  "codigo": "S1",
  "cantidad": 50,
  "estado": "Disponible"  // opcional, default: "Disponible"
}
```

✅ **Compatible** - El campo `estado` es opcional en tu endpoint.

## ✅ Checklist de Implementación

- [ ] Determinar IP correcta (Tailscale/VPC/Pública)
- [ ] Editar `fabricacion-api/compose.yaml` línea 31
- [ ] Reiniciar servicio: `docker compose restart api`
- [ ] Verificar logs de fábrica: `docker compose logs -f api`
- [ ] Crear orden de prueba
- [ ] Verificar logs de inventario: `sudo docker compose logs -f api`
- [ ] Confirmar orden completada automáticamente
- [ ] Confirmar inventario actualizado
- [ ] Documentar IP usada para futuras referencias

## 🎉 Resultado Esperado

Una vez configurado correctamente:

1. Creas orden → Estado: `"confirmado"`
2. Fábrica fabrica (5-10 seg)
3. Fábrica envía webhook → Tu servidor recibe
4. Inventario se actualiza automáticamente
5. Orden cambia a estado: `"completada"`

**¡Todo automático sin intervención manual!** 🚀
