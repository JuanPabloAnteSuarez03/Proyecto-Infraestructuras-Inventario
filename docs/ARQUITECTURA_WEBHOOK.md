# 🏗️ Arquitectura del Sistema - Webhook Fabricación

## 📊 Diagrama de Arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│                     SERVIDOR INVENTARIO                           │
│                  (Tu máquina / Cloud server)                      │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Docker Compose                                            │  │
│  │                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │  │
│  │  │              │  │              │  │              │   │  │
│  │  │   FastAPI    │  │   Worker     │  │  PostgreSQL  │   │  │
│  │  │     API      │  │   (RQ)       │  │      DB      │   │  │
│  │  │   :5050      │  │              │  │   :5432      │   │  │
│  │  │              │  │              │  │              │   │  │
│  │  └──────┬───────┘  └──────────────┘  └──────────────┘   │  │
│  │         │                                                 │  │
│  │         │ Endpoints:                                     │  │
│  │         │ • POST /api/fabricacion/ordenes                │  │
│  │         │ • POST /api/productos/ingresos ◄────┐          │  │
│  │         │ • POST /api/fabricacion/webhook/... │          │  │
│  │         │                                      │          │  │
│  └─────────┼──────────────────────────────────────┼──────────┘  │
│            │                                      │              │
│            │ HTTP Request                         │              │
│            │ (Crear orden)                        │              │
│            ▼                                      │              │
└────────────┼──────────────────────────────────────┼──────────────┘
             │                                      │
             │                                      │ HTTP POST
             │                                      │ (Webhook)
             │                                      │
┌────────────┼──────────────────────────────────────┼──────────────┐
│            │         SERVIDOR AWS                 │              │
│            │   ec2-98-93-67-35.compute-1...       │              │
│            │                                      │              │
│  ┌─────────┼──────────────────────────────────────┼───────────┐  │
│  │ Docker  │ Compose                              │           │  │
│  │         │                                      │           │  │
│  │  ┌──────▼───────┐  ┌──────────────┐  ┌────────┴────────┐ │  │
│  │  │              │  │              │  │                 │ │  │
│  │  │   FastAPI    │  │  PostgreSQL  │  │   Fabrication   │ │  │
│  │  │ Fabricacion  │  │      DB      │  │     Workers     │ │  │
│  │  │   :8555      │  │   :5432      │  │  (ThreadPool)   │ │  │
│  │  │              │  │              │  │                 │ │  │
│  │  │  Endpoints:  │  │              │  │  • Simula       │ │  │
│  │  │  • /planos   │  │              │  │    fabricación  │ │  │
│  │  │  • /calcular │  │              │  │  • Envía        │ │  │
│  │  │  • /confirmar│  │              │  │    webhook      │ │  │
│  │  │              │  │              │  │                 │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘ │  │
│  │                                                           │  │
│  │  Environment:                                            │  │
│  │  API_PATH_INVENTARIO=http://IP:5050/api/productos/...   │  │
│  │                           ^^                             │  │
│  │                           └─ AQUÍ ESTÁ EL PROBLEMA       │  │
│  │                              (IP incorrecta)             │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 🔄 Flujo de Comunicación Completo

### 1️⃣ Creación de Orden

```
[Cliente/Usuario]
      │
      │ POST /api/fabricacion/ordenes
      │ {"id_producto": "S1", "cantidad": 100}
      ▼
[API Inventario :5050]
      │
      │ 1. Calcular piezas necesarias
      │ 2. Verificar inventario de piezas
      │ 3. Solicitar a proveedores si falta
      │
      │ POST /fabricacion/confirmar_fabricacion
      │ {"codigo": "S1", "cantidad": 100}
      ▼
[API Fabricación AWS :8555]
      │
      │ 1. Validar plano existe
      │ 2. Encolar trabajo en fabrication_queue
      │ 3. Responder {"status": "ok"}
      ▼
[API Inventario :5050]
      │
      │ 1. Cambiar orden a "confirmado"
      │ 2. Encolar worker RQ
      │ 3. Responder al cliente
      ▼
[Cliente/Usuario]
   {"id": 25, "estado": "confirmado", "tiempo_estimado": 9}
```

### 2️⃣ Procesamiento en Background

```
[API Fabricación AWS :8555]
      │
      │ fabrication_queue procesa trabajo
      ▼
[Fabrication Worker]
      │
      │ 1. Simular fabricación (time.sleep)
      │ 2. Construir payload:
      │    {"codigo": "S1", "cantidad": 100}
      │
      │ POST {API_PATH_INVENTARIO}
      │      ▼
      │      httpx.post(url, json=data)
      │
      ├──── ✅ SI IP ES CORRECTA ────┐
      │                               │
      │                               ▼
      │                    [API Inventario :5050]
      │                               │
      │                               │ POST /api/productos/ingresos
      │                               │ {"codigo": "S1", "cantidad": 100}
      │                               │
      │                               │ 1. Incrementar inventario
      │                               │ 2. Buscar órdenes pendientes
      │                               │ 3. Completar orden #25
      │                               │
      │                               ▼
      │                    [Base de Datos]
      │                    • S1 Disponible: +100
      │                    • Orden #25: "completada" ✅
      │
      └──── ❌ SI IP ES INCORRECTA ───┐
                                       │
                                       ▼
                            [IP 100.100.74.70] (no existe)
                                       │
                                       │ Connection timeout/refused
                                       ▼
                            [Worker imprime error]
                            "[ERROR] Falló actualización inventario"
                                       │
                                       ▼
                            [Orden #25 queda en "esperando_fabricacion" ❌]
                            [Inventario NO se actualiza ❌]
```

## 🔍 Detalle de los Componentes

### API Inventario (Puerto 5050)

**Tecnología:** FastAPI + SQLAlchemy + PostgreSQL + RQ (Redis Queue)

**Responsabilidades:**
- Gestionar inventario de productos y piezas
- Crear órdenes de fabricación
- Confirmar órdenes con fábrica externa
- **Recibir webhooks** de productos terminados
- Completar órdenes automáticamente

**Endpoints clave:**
```python
# Crear orden (sincrónico)
POST /api/fabricacion/ordenes
→ Llama a fábrica externa
→ Encola worker local
→ Retorna orden confirmada

# Recibir productos (webhook)
POST /api/productos/ingresos
→ Incrementa inventario
→ Completa órdenes pendientes
→ Retorna estado actualizado
```

### API Fabricación AWS (Puerto 8555)

**Tecnología:** FastAPI + SQLAlchemy + PostgreSQL + AsyncIO Queue + ThreadPoolExecutor

**Responsabilidades:**
- Proveer información de planos (S1, S2)
- Calcular piezas necesarias
- Confirmar órdenes de fabricación
- **Ejecutar fabricación en background**
- **Enviar webhooks** cuando termina

**Componentes clave:**
```python
# 1. Cola asíncrona global
fabrication_queue = AsyncQueue()

# 2. Pool de workers (6 threads)
executor = ThreadPoolExecutor(max_workers=6)

# 3. Worker que procesa fabricación
def worker_fabricacion(codigo: str, cantidad: int):
    # Simular fabricación
    for i in range(cantidad):
        time.sleep(1/24)  # ~4 segundos por 100 unidades

    # ENVIAR WEBHOOK
    url = API_PATH_INVENTARIO  # Variable de entorno
    data = {"codigo": codigo, "cantidad": cantidad}
    httpx.post(url, json=data)
```

## 🔐 Configuración de Red

### Opciones de Conectividad

#### Opción 1: Tailscale VPN ✅ Recomendado

```yaml
# fabricacion-api/compose.yaml
API_PATH_INVENTARIO: http://100.70.143.89:5050/api/productos/ingresos
```

**Requisitos:**
- Ambos servidores deben tener Tailscale instalado
- Ambos deben estar en la misma red Tailscale (tailnet)

**Ventajas:**
- ✅ Encriptación automática (WireGuard)
- ✅ Funciona a través de NAT/firewalls
- ✅ No necesitas abrir puertos públicos
- ✅ IPs relativamente estables
- ✅ Gratis para uso personal (hasta 100 dispositivos)

**Verificar conectividad:**
```bash
# Desde servidor AWS
curl -v http://100.70.143.89:5050/health
```

#### Opción 2: VPC Privada AWS

```yaml
# fabricacion-api/compose.yaml
API_PATH_INVENTARIO: http://172.31.10.50:5050/api/productos/ingresos
```

**Requisitos:**
- Ambos servidores EC2 en la misma VPC
- Security Groups configurados correctamente

**Ventajas:**
- ✅ Latencia mínima
- ✅ Sin costos de transferencia entre AZs
- ✅ Máxima seguridad (red privada)

#### Opción 3: IP Pública

```yaml
# fabricacion-api/compose.yaml
API_PATH_INVENTARIO: http://186.27.169.195:5050/api/productos/ingresos
```

**Requisitos:**
- Servidor inventario con IP pública estática/elástica
- Puerto 5050 abierto en firewall

```bash
# En servidor inventario
sudo ufw allow 5050/tcp
# O en AWS Security Group: Inbound Rule TCP 5050 from anywhere
```

**Desventajas:**
- ⚠️ Expone el servicio al público
- ⚠️ Requiere gestión de firewall
- ⚠️ IP dinámica puede cambiar (usar IP elástica)

## 📝 Variables de Entorno Críticas

### Servidor Inventario (.env)

```bash
# URL de la fábrica externa (para hacer requests)
FABRICA_BASE_URL=http://ec2-98-93-67-35.compute-1.amazonaws.com:8555

# URL callback (opcional, no se usa actualmente)
WEBHOOK_CALLBACK_URL=http://100.70.143.89:5050/api/productos/ingresos
```

### Servidor Fabricación AWS (compose.yaml)

```yaml
services:
  api:
    environment:
      # ⚠️ VARIABLE CRÍTICA - Controla a dónde se envían webhooks
      API_PATH_INVENTARIO: http://100.70.143.89:5050/api/productos/ingresos
      #                          ^^^^^^^^^^^^^^
      #                          Esta IP DEBE ser accesible desde AWS
```

## 🧪 Pruebas de Conectividad

### Desde Servidor AWS → Inventario

```bash
# SSH al servidor AWS
ssh usuario@ec2-98-93-67-35.compute-1.amazonaws.com

# Probar health endpoint
curl -v http://100.70.143.89:5050/health

# Probar endpoint de webhook
curl -X POST http://100.70.143.89:5050/api/productos/ingresos \
  -H "Content-Type: application/json" \
  -d '{"codigo": "S1", "cantidad": 10}'

# Debería retornar 200 OK con:
# {"id_producto": "S1", "cantidad": 110, ...}
```

### Desde Inventario → AWS

```bash
# En servidor inventario
curl -v http://ec2-98-93-67-35.compute-1.amazonaws.com:8555/fabricacion/planos/1

# Debería retornar 200 OK con:
# {"id": 1, "nombre": "Sierra Clásica", "tiempo_fabricacion": 1, ...}
```

## 🐛 Troubleshooting

### Problema: Webhooks no llegan

**Síntomas:**
- Orden queda en `"esperando_fabricacion"` indefinidamente
- Inventario no se actualiza

**Diagnóstico:**
```bash
# 1. Ver logs de worker en AWS
ssh usuario@ec2-98-93-67-35.compute-1.amazonaws.com
cd fabricacion-api
docker compose logs -f api | grep -i "inventario\|error"

# Buscar:
# ✅ "200" → Webhook llegó correctamente
# ❌ "[ERROR] Falló actualización inventario" → No llegó
```

**Soluciones:**
1. Verificar IP en `API_PATH_INVENTARIO`
2. Verificar conectividad desde AWS
3. Verificar firewall/security groups
4. Verificar que servicio inventario esté corriendo

### Problema: Connection timeout

**Síntomas:**
- Logs de AWS muestran timeout
- Webhook tarda mucho

**Causas comunes:**
- Firewall bloqueando puerto 5050
- IP incorrecta o no alcanzable
- Servicio inventario caído

**Verificar:**
```bash
# En servidor inventario
sudo docker compose ps  # Verificar que 'api' esté 'Up'
sudo ufw status        # Verificar puerto 5050 abierto
ss -tlnp | grep 5050   # Verificar que puerto escucha
```

## 📊 Monitoreo

### Logs en Tiempo Real

**Servidor Inventario:**
```bash
# Ver todos los webhooks entrantes
sudo docker compose logs -f api | grep -E "POST /api/productos/ingresos|INGRESO"

# Salida esperada cuando llega webhook:
# [INGRESO] ✓ Orden #25 completada. Pedido: 100, recibido total: 100
```

**Servidor Fabricación AWS:**
```bash
# Ver cuando se envían webhooks
docker compose logs -f api | grep -E "worker_fabricacion|inventario"

# Salida esperada cuando se envía webhook:
# 200  (código HTTP de respuesta exitosa)
```

## 🎯 Checklist de Implementación

- [ ] Determinar método de conectividad (Tailscale/VPC/Pública)
- [ ] Obtener IP correcta del servidor inventario
- [ ] SSH al servidor AWS donde corre fabricacion-api
- [ ] Editar `fabricacion-api/compose.yaml` línea 31
- [ ] Actualizar `API_PATH_INVENTARIO` con IP correcta
- [ ] Reiniciar servicio: `docker compose restart api`
- [ ] Probar conectividad: `curl http://IP:5050/health`
- [ ] Crear orden de prueba en servidor inventario
- [ ] Monitorear logs en ambos servidores
- [ ] Verificar orden completada automáticamente
- [ ] Verificar inventario actualizado
- [ ] Documentar configuración para referencia futura
