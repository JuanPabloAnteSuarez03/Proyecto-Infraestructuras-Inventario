# 🔧 Configuración Completa - Integración Fábrica ↔ Inventario

## 📋 Estado Actual

### ✅ Lo que YA funciona

**Servicio de Fábrica (AWS):**
- ✅ API funcionando en `http://ec2-98-93-67-35.compute-1.amazonaws.com:8555`
- ✅ Worker de fabricación implementado (`fabricacion_workers.py`)
- ✅ Cola asíncrona operativa (`queue_fabricacion.py`)
- ✅ Envío de webhooks implementado (línea 21 de `fabricacion_workers.py`)
- ✅ Configuración: `API_PATH_INVENTARIO` en `compose.yaml`

**Servicio de Inventario (Tu servidor):**
- ✅ API funcionando en puerto 5050
- ✅ Endpoint webhook implementado: `/api/productos/ingresos`
- ✅ Lógica de actualización automática de inventario
- ✅ Lógica de completar órdenes automáticamente

### ❌ Lo que FALTA

1. **Configurar IP correcta en fabricacion-api** (lado de AWS)
2. **Exponer tu servicio de inventario** (tu lado)
3. **Probar conectividad**

---

## 🎯 SOLUCIÓN: 2 Configuraciones Necesarias

## Parte 1: Configurar Fábrica (AWS) ✅

### Opción A: Si usas Tailscale (RECOMENDADO)

**Requisitos:**
- Ambos servidores deben tener Tailscale instalado
- Ambos en la misma red Tailscale (tailnet)

**Pasos:**

1. **Verificar IP Tailscale de tu servidor inventario:**
```bash
# En tu servidor de inventario
ip addr show tailscale0
# O ver en: https://login.tailscale.com/admin/machines
# Tu IP Tailscale: 100.70.143.89
```

2. **Verificar que servidor AWS también tiene Tailscale:**
```bash
# SSH al servidor AWS
ssh usuario@ec2-98-93-67-35.compute-1.amazonaws.com

# Verificar Tailscale
ip addr show tailscale0
# Debería mostrar una IP 100.x.x.x
```

3. **Editar configuración de fábrica:**
```bash
# En servidor AWS
cd fabricacion-api
nano compose.yaml  # O vim

# Cambiar línea 31:
API_PATH_INVENTARIO: http://100.70.143.89:5050/api/productos/ingresos

# Guardar: Ctrl+X, Y, Enter
```

4. **Reiniciar fábrica:**
```bash
docker compose restart api
docker compose logs -f api
```

5. **Probar conectividad desde AWS:**
```bash
# Desde el servidor AWS
curl -v http://100.70.143.89:5050/health

# Debería retornar: {"status": "ok"}
```

✅ **Si el curl funciona, ya está listo** - Pasa a la Parte 2

❌ **Si el curl falla**, prueba la Opción B

---

### Opción B: Si ambos están en misma VPC AWS

**Requisitos:**
- Ambos servidores EC2 en AWS
- Misma región y VPC

**Pasos:**

1. **Obtener IP privada de tu servidor inventario:**
```bash
# En tu servidor de inventario (EC2)
hostname -I
# Ej: 172.31.10.50
```

2. **Configurar Security Group:**
```bash
# En AWS Console:
# 1. Ve a EC2 → Security Groups
# 2. Selecciona el SG de tu servidor inventario
# 3. Inbound Rules → Add Rule:
#    - Type: Custom TCP
#    - Port: 5050
#    - Source: Security Group del servidor AWS fabricacion
```

3. **Editar configuración de fábrica:**
```bash
# En servidor AWS
cd fabricacion-api
nano compose.yaml

# Cambiar línea 31:
API_PATH_INVENTARIO: http://172.31.10.50:5050/api/productos/ingresos
#                          ^^^^^^^^^^^^
#                          Tu IP privada VPC

# Guardar y reiniciar
docker compose restart api
```

4. **Probar conectividad:**
```bash
# Desde servidor AWS
curl -v http://172.31.10.50:5050/health
```

---

### Opción C: Usar IP Pública (NO RECOMENDADO)

**⚠️ Solo si las opciones A y B no son posibles**

**Requisitos:**
- Tu servidor inventario debe tener IP pública
- Debes abrir puerto 5050 al público

**Pasos:**

1. **Obtener IP pública:**
```bash
# En tu servidor inventario
curl ifconfig.me
# Ej: 186.27.169.195
```

2. **Abrir puerto en firewall:**
```bash
# Opción 1: UFW (Ubuntu/Debian)
sudo ufw allow 5050/tcp
sudo ufw status

# Opción 2: iptables
sudo iptables -A INPUT -p tcp --dport 5050 -j ACCEPT
sudo iptables-save

# Opción 3: AWS Security Group
# EC2 → Security Groups → Inbound Rules
# Add: TCP 5050 from 0.0.0.0/0
```

3. **Verificar puerto abierto:**
```bash
# En tu servidor inventario
sudo ss -tlnp | grep 5050
# Debe mostrar: LISTEN en 0.0.0.0:5050
```

4. **Editar configuración de fábrica:**
```bash
# En servidor AWS
cd fabricacion-api
nano compose.yaml

# Cambiar línea 31:
API_PATH_INVENTARIO: http://186.27.169.195:5050/api/productos/ingresos

# Guardar y reiniciar
docker compose restart api
```

5. **Probar conectividad:**
```bash
# Desde cualquier máquina
curl -v http://186.27.169.195:5050/health
```

---

## Parte 2: Configurar tu Servicio de Inventario ✅

Tu servicio YA está funcionando, solo necesitas asegurar que:

### 1. Verificar que el servicio está corriendo

```bash
# Ver contenedores activos
sudo docker compose ps

# Deberías ver:
# NAME    IMAGE    STATUS
# api     ...      Up
# worker  ...      Up
# db      ...      Up
```

### 2. Verificar que el puerto está expuesto

```bash
# Ver puertos escuchando
sudo ss -tlnp | grep 5050

# Debe mostrar:
# LISTEN 0.0.0.0:5050
```

### 3. Verificar firewall local

```bash
# Ver reglas UFW
sudo ufw status

# Si 5050 NO aparece:
sudo ufw allow 5050/tcp
```

### 4. Probar endpoint de webhook localmente

```bash
# Simular que la fábrica envía productos
curl -X POST http://localhost:5050/api/productos/ingresos \
  -H "Content-Type: application/json" \
  -d '{"codigo": "S1", "cantidad": 10}'

# Debe retornar:
# {
#   "id_producto": "S1",
#   "estado": "Disponible",
#   "cantidad": 10
# }
```

### 5. Verificar logs en tiempo real

```bash
# Abrir terminal para monitorear webhooks
sudo docker compose logs -f api | grep -E "POST /api/productos/ingresos|INGRESO"

# Dejar esta terminal abierta durante las pruebas
```

---

## 🧪 Prueba de Integración Completa

Una vez configurado todo:

### 1. Resetear inventario (opcional)

```bash
sudo docker compose exec api python -m app.cli reset-inventory
```

### 2. Verificar conectividad de fábrica → inventario

```bash
# Desde servidor AWS donde corre fabricacion-api
curl -v http://TU_IP:5050/health
curl -v http://TU_IP:5050/api/productos

# Ambos deben responder 200 OK
```

### 3. Crear orden de fabricación

```bash
# En tu servidor de inventario
curl -X POST http://localhost:5050/api/fabricacion/ordenes \
  -H "Content-Type: application/json" \
  -d '{"id_producto": "S1", "cantidad": 50}'

# Debería retornar:
# {
#   "id": 25,
#   "estado": "confirmado",
#   "tiempo_estimado": 9,
#   "detalle": {
#     "pasos": ["✓ Fábrica externa confirmó la orden"],
#     "confirmacion_fabrica": {"status": "ok"}
#   }
# }
```

### 4. Monitorear logs en AMBOS servidores

**Terminal 1 (Tu servidor inventario):**
```bash
sudo docker compose logs -f api | grep -E "INGRESO|webhook"
```

**Terminal 2 (Servidor AWS fabricacion):**
```bash
# SSH al servidor
ssh usuario@ec2-98-93-67-35.compute-1.amazonaws.com
cd fabricacion-api
docker compose logs -f api | grep -E "Fabricado|inventario"
```

### 5. Esperar ~5-10 segundos

La fabricación toma tiempo (1/24 seg por unidad):
- 50 unidades = ~2 segundos
- 100 unidades = ~4 segundos
- 500 unidades = ~21 segundos

### 6. Verificar que la orden se completó AUTOMÁTICAMENTE

```bash
# Ver estado de la orden
curl -s http://localhost:5050/api/fabricacion/ordenes | \
  python -m json.tool | grep -A10 '"id": 25'

# Debe mostrar:
# "estado": "completada"  ✅
```

### 7. Verificar que el inventario se actualizó

```bash
curl -s http://localhost:5050/api/productos | \
  python -m json.tool | grep -A3 '"id_producto": "S1"'

# Debe mostrar:
# "cantidad": 50  (o más si había stock previo)
```

---

## ✅ Criterios de Éxito

La integración funciona correctamente si:

1. ✅ La orden cambia automáticamente a `"estado": "completada"`
2. ✅ El inventario se incrementa automáticamente
3. ✅ No ves errores en los logs
4. ✅ Los logs muestran:
   - AWS: `200` (código HTTP exitoso)
   - Inventario: `[INGRESO] ✓ Orden #X completada`

---

## 🐛 Troubleshooting

### Problema: Orden queda en "esperando_fabricacion"

**Diagnóstico:**
```bash
# Ver logs de fábrica (AWS)
docker compose logs api | tail -50 | grep -i error

# Buscar:
# "[ERROR] Falló actualización inventario"
```

**Solución:**
- Verificar IP en `API_PATH_INVENTARIO`
- Verificar conectividad: `curl http://IP:5050/health`
- Verificar firewall/security groups

### Problema: Connection timeout

**Causas:**
- Firewall bloqueando puerto 5050
- IP incorrecta
- Servicio inventario caído
- Security Group AWS mal configurado

**Verificar:**
```bash
# Firewall
sudo ufw status | grep 5050

# Puerto escuchando
sudo ss -tlnp | grep 5050

# Servicio corriendo
sudo docker compose ps
```

### Problema: Connection refused

**Causas:**
- Servicio no está corriendo
- Puerto no está expuesto en docker-compose.yml

**Verificar docker-compose.yml:**
```yaml
services:
  api:
    ports:
      - "5050:8000"  # ✅ Debe estar presente
```

---

## 📊 Resumen de IPs y Puertos

| Servicio | URL | Puerto | Acceso |
|----------|-----|--------|--------|
| Fábrica AWS | `ec2-98-93-67-35.compute-1.amazonaws.com` | 8555 | Público |
| Inventario (local) | `localhost` | 5050 | Local |
| Inventario (Tailscale) | `100.70.143.89` | 5050 | VPN |
| Inventario (VPC) | `172.31.x.x` | 5050 | Privado AWS |
| Inventario (Público) | `186.27.169.195` | 5050 | Internet |

## 🎯 Recomendaciones Finales

**Para Desarrollo/Pruebas:**
- ✅ Usar Tailscale (más fácil, seguro, sin configuración de firewall)

**Para Producción:**
- ✅ Si ambos en AWS: Usar IPs privadas VPC
- ✅ Si geografías diferentes: Usar Tailscale o VPN dedicada
- ⚠️ Evitar IP pública si es posible (menos seguro)

**Seguridad:**
- Nunca uses IP pública sin autenticación
- Considera agregar API key/token en headers
- Usa HTTPS en producción (detrás de nginx/load balancer)

---

## 📞 Siguiente Paso

1. Elegir método de conectividad (Tailscale recomendado)
2. Seguir los pasos de la **Opción A, B o C** en Parte 1
3. Verificar la Parte 2 (tu servicio ya debería estar OK)
4. Ejecutar la **Prueba de Integración Completa**
5. Si todo funciona: ¡Listo! 🎉
6. Si hay problemas: Revisar **Troubleshooting**
