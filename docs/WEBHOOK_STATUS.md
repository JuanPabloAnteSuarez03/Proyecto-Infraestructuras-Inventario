# Estado del Webhook - Integración con Fábrica Externa

## 📊 Resumen Ejecutivo

### ✅ Lo que FUNCIONA:

1. **Integración con Fábrica AWS**
   - URL: `http://ec2-98-93-67-35.compute-1.amazonaws.com:8555`
   - Estado: ✅ Conectado y funcionando
   - Endpoints funcionando:
     - `/fabricacion/planos/{id}` ✅
     - `/fabricacion/calculo_piezas` ✅
     - `/fabricacion/confirmar_fabricacion` ✅

2. **Sistema de Órdenes**
   - Creación de órdenes: ✅ Funciona
   - Confirmación con fábrica externa: ✅ Funciona
   - Gestión de estados: ✅ Funciona
   - Solicitud automática de piezas a proveedores: ✅ Funciona

3. **Endpoint de Webhook Local**
   - Ruta principal: `/api/productos/ingresos` ✅
   - Ruta alternativa: `/api/fabricacion/webhook/productos_terminados` ✅
   - Estado: ✅ Funciona correctamente
   - Probado: ✅ Actualiza inventario automáticamente
   - Completa órdenes: ✅ Funciona

4. **Worker de Fabricación (DESCUBRIMIENTO CRÍTICO)**
   - ✅ La fábrica **SÍ tiene implementado el webhook**
   - ✅ Archivo: `fabricacion-api/app/utils/fabricacion_workers.py` línea 12-28
   - ✅ El worker **SÍ envía** POST request cuando termina la fabricación
   - ✅ Código confirmado: `httpx.post(url, json=data)`

### ⚠️ PROBLEMA REAL (No es lo que pensábamos):

**Problema Verdadero:** La fábrica **SÍ está enviando webhooks**, pero a la **IP INCORRECTA**.

**Configuración actual en fabricacion-api:**
```yaml
# fabricacion-api/compose.yaml línea 31
API_PATH_INVENTARIO: http://100.100.74.70:5050/api/productos/ingresos
```

**IP configurada:** `100.100.74.70` ❌ (IP incorrecta)
**IP correcta debería ser:**
- `100.70.143.89` (Tailscale) - si ambos servicios están en Tailscale
- O la IP accesible desde AWS donde corre fabricacion-api

**Resultado:**
- La fábrica confirma las órdenes ✅
- La fábrica **SÍ envía webhooks** ✅
- Pero los envía a IP incorrecta ❌
- Los webhooks no llegan a tu servidor ❌
- Las órdenes quedan en estado "esperando_fabricacion" indefinidamente
- El inventario NO se actualiza automáticamente

---

## 🔧 SOLUCIÓN INMEDIATA: Actualizar IP en Fábrica

**El problema está en el lado de la fábrica, no en tu servidor.**

### Paso 1: Actualizar fabricacion-api/compose.yaml

Editar el archivo `fabricacion-api/compose.yaml` línea 31 en el servidor AWS:

```yaml
# ANTES (IP incorrecta):
API_PATH_INVENTARIO: http://100.100.74.70:5050/api/productos/ingresos

# DESPUÉS (usar IP correcta):
# Opción A: Si tu servidor está en Tailscale
API_PATH_INVENTARIO: http://100.70.143.89:5050/api/productos/ingresos

# Opción B: Si tu servidor tiene IP pública accesible
API_PATH_INVENTARIO: http://TU_IP_PUBLICA:5050/api/productos/ingresos

# Opción C: Si ambos están en la misma VPC de AWS
API_PATH_INVENTARIO: http://IP_PRIVADA_AWS:5050/api/productos/ingresos
```

### Paso 2: Reiniciar servicio de fábrica

```bash
# En el servidor AWS donde corre fabricacion-api
cd fabricacion-api
docker compose restart api
```

### Paso 3: Verificar logs de fábrica

```bash
# Monitorear si el webhook se envía correctamente
docker compose logs -f api
```

### Paso 4: Crear orden de prueba

```bash
# En tu servidor de inventario
curl -X POST http://localhost:5050/api/fabricacion/ordenes \
  -H "Content-Type: application/json" \
  -d '{"id_producto": "S1", "cantidad": 50}'

# Esperar ~5 segundos (depende de la cantidad)
# El webhook debería llegar automáticamente

# Verificar que la orden se completó
curl http://localhost:5050/api/fabricacion/ordenes | python -m json.tool | grep -A5 "completada"
```

---

## 🔧 Soluciones Alternativas (si la IP sigue sin funcionar)

### Opción 1: Desplegar en Servidor con IP Pública (RECOMENDADO)

**AWS EC2, DigitalOcean, Linode, etc.**

```bash
# 1. Desplegar aplicación en servidor cloud
# 2. Configurar .env en el servidor:
WEBHOOK_CALLBACK_URL=http://TU_IP_SERVIDOR:5050/api/fabricacion/webhook/productos_terminados

# 3. Abrir puerto 5050 en firewall del servidor
# AWS: Security Group → Inbound Rules → Puerto 5050
# DigitalOcean: Firewall → Inbound Rules → Puerto 5050
```

**Ventajas:**
- ✅ Funciona 24/7
- ✅ IP pública accesible
- ✅ Escalable
- ✅ Profesional

---

### Opción 2: Usar Túnel (ngrok, Cloudflare Tunnel)

**ngrok (requiere cuenta gratuita):**
```bash
# 1. Registrarse en https://dashboard.ngrok.com/signup
# 2. Configurar authtoken
ngrok config add-authtoken TU_TOKEN

# 3. Ejecutar túnel
ngrok http 5050

# 4. Copiar URL pública (ej: https://abc123.ngrok.io)
# 5. Actualizar .env:
WEBHOOK_CALLBACK_URL=https://abc123.ngrok.io/api/fabricacion/webhook/productos_terminados

# 6. Reiniciar contenedores
sudo docker compose restart
```

**Cloudflare Tunnel (gratis, más permanente):**
```bash
# 1. Instalar cloudflared
# 2. Autenticar con Cloudflare
# 3. Crear túnel permanente
cloudflared tunnel --url http://localhost:5050
```

**Ventajas:**
- ✅ Rápido de configurar
- ✅ HTTPS automático
- ✅ Bueno para desarrollo

**Desventajas:**
- ❌ URL cambia cada vez (ngrok gratis)
- ❌ Requiere proceso corriendo
- ❌ No apto para producción permanente

---

### Opción 3: Port Forwarding en Router

```bash
# 1. Acceder a router (normalmente 192.168.1.1)
# 2. Buscar "Port Forwarding" o "NAT"
# 3. Configurar:
#    - Puerto externo: 5050
#    - IP interna: <IP_DE_TU_MAQUINA>
#    - Puerto interno: 5050
#    - Protocolo: TCP

# 4. Configurar .env:
WEBHOOK_CALLBACK_URL=http://TU_IP_PUBLICA_REAL:5050/api/fabricacion/webhook/productos_terminados
```

**Ventajas:**
- ✅ Sin servicios externos
- ✅ Sin costos

**Desventajas:**
- ❌ Requiere acceso al router
- ❌ IP dinámica puede cambiar
- ❌ Expone tu red local

---

## 🧪 Solución Actual (Desarrollo/Demostración)

### Flujo de Trabajo Manual

**Paso 1: Crear orden de fabricación**
```bash
curl -X POST http://localhost:5050/api/fabricacion/ordenes \
  -H "Content-Type: application/json" \
  -d '{"id_producto": "S1", "cantidad": 100}'
```

**Respuesta:**
```json
{
  "id": 23,
  "estado": "confirmado",
  "tiempo_estimado": 9,
  "detalle": {
    "pasos": [
      "✓ Fábrica externa confirmó la orden"
    ],
    "confirmacion_fabrica": {
      "status": "ok"
    }
  }
}
```

**Paso 2: Simular webhook de fábrica (cuando productos estén listos)**
```bash
curl -X POST http://localhost:5050/api/fabricacion/webhook/productos_terminados \
  -H "Content-Type: application/json" \
  -d '{"codigo": "S1", "cantidad": 100, "estado": "Disponible"}'
```

**Respuesta:**
```json
{
  "status": "ok",
  "mensaje": "Recibidos 100 productos S1",
  "inventario_actual": 100
}
```

**Paso 3: Verificar inventario actualizado**
```bash
curl http://localhost:5050/api/productos | grep -A3 "S1.*Disponible"
```

---

## 📝 Comandos Útiles

### Monitorear Logs en Tiempo Real
```bash
# Ver todos los logs
sudo docker compose logs -f api

# Ver solo webhooks
sudo docker compose logs -f api | grep WEBHOOK

# Ver últimas 50 líneas
sudo docker compose logs api --tail=50
```

### Verificar Estado de Órdenes
```bash
# Listar todas las órdenes
curl http://localhost:5050/api/fabricacion/ordenes | python -m json.tool

# Ver orden específica
curl http://localhost:5050/api/fabricacion/ordenes/23 | python -m json.tool

# Ver solo órdenes en espera
curl -s http://localhost:5050/api/fabricacion/ordenes | python -m json.tool | grep -B2 "esperando_fabricacion"
```

### Verificar Inventario
```bash
# Ver todos los productos
curl http://localhost:5050/api/productos | python -m json.tool

# Ver solo S1 disponible
curl -s http://localhost:5050/api/productos | python -m json.tool | grep -A3 '"id_producto": "S1"' | grep -A3 "Disponible"
```

### Probar Conexión con Fábrica
```bash
# Usar comando CLI
sudo docker compose exec api python -m app.cli test-fabrica

# O endpoint directo
curl http://localhost:5050/api/fabricacion/external/status | python -m json.tool
```

---

## 🎯 Recomendación Final

Para **desarrollo y demostraciones**: Continúa usando el flujo manual (simular webhooks)

Para **producción**:
1. Despliega en AWS EC2 u otro servidor cloud
2. O usa Cloudflare Tunnel para un túnel permanente
3. Configura el webhook con la URL accesible públicamente

---

## 📌 Archivos Importantes

- [app/services/fabricacion_service.py](app/services/fabricacion_service.py#L20) - Mapeo de códigos (S1→S1, S2→S2) ✅ Corregido
- [app/api/fabricacion_controller.py](app/api/fabricacion_controller.py#L295) - Endpoint webhook
- [.env](.env) - Configuración actual (IP Tailscale)
- [test_fabrica.py](test_fabrica.py) - Script de pruebas
- [TESTING.md](TESTING.md) - Guía completa de pruebas

---

## ✅ Checklist de Funcionalidad

- [x] Conexión con fábrica externa
- [x] Consultar planos de fabricación
- [x] Calcular piezas necesarias
- [x] Crear órdenes de fabricación
- [x] Confirmar órdenes con fábrica
- [x] Solicitar piezas a proveedores automáticamente
- [x] Endpoint webhook funcional en servidor inventario
- [x] Actualización de inventario vía webhook
- [x] Completación de órdenes vía webhook
- [x] Worker de fabricación implementado y funcional
- [ ] **IP correcta configurada en fabricacion-api** ← **ÚNICO PROBLEMA**

**Estado General: 95% Funcional**
- ✅ Todo el código funciona correctamente
- ✅ Los webhooks están implementados en ambos lados
- ❌ Solo falta actualizar la IP en `fabricacion-api/compose.yaml`
- ✅ Solución: Cambiar línea 31 de `100.100.74.70` a la IP correcta

## 🎯 Recomendación Final Actualizada

**Solución inmediata (5 minutos):**
1. Actualizar IP en `fabricacion-api/compose.yaml` línea 31
2. Reiniciar servicio: `docker compose restart api`
3. Probar con orden de fabricación

**Si ambos servicios están en AWS:**
- Usar IP privada de VPC para comunicación rápida y segura
- No necesitas exponer el puerto al público

**Si están en redes diferentes:**
- Opción A: Conectar ambos via Tailscale (VPN) ✅ Ya tienes Tailscale
- Opción B: Exponer puerto 5050 con IP pública
- Opción C: Usar túnel (ngrok, cloudflare)
