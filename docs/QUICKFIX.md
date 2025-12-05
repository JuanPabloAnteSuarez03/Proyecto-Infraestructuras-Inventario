# ⚡ Quick Fix - Webhook Fabricación (1 minuto)

## 🎯 El Problema

Los webhooks de la fábrica **NO LLEGAN** porque la IP configurada es incorrecta.

## ✅ La Solución (3 pasos)

### 1. SSH al servidor AWS

```bash
ssh usuario@ec2-98-93-67-35.compute-1.amazonaws.com
```

### 2. Editar la configuración

```bash
cd fabricacion-api
nano compose.yaml  # O usar vim
```

**Cambiar línea 31:**

```yaml
# ANTES (❌ incorrecta):
API_PATH_INVENTARIO: http://100.100.74.70:5050/api/productos/ingresos

# DESPUÉS (✅ correcta - Tailscale):
API_PATH_INVENTARIO: http://100.70.143.89:5050/api/productos/ingresos
```

**Guardar:** Ctrl+X, Y, Enter (en nano)

### 3. Reiniciar servicio

```bash
docker compose restart api
docker compose logs -f api  # Monitorear
```

## 🧪 Probar que funciona

```bash
# En tu servidor de inventario

# 1. Crear orden
curl -X POST http://localhost:5050/api/fabricacion/ordenes \
  -H "Content-Type: application/json" \
  -d '{"id_producto": "S1", "cantidad": 50}'

# 2. Esperar 5-10 segundos

# 3. Verificar que completó automáticamente
curl http://localhost:5050/api/fabricacion/ordenes | python -m json.tool | grep completada
```

**✅ Si ves `"estado": "completada"` → Funcionó**

## 📚 Más Info

- **[CONFIGURACION_COMPLETA.md](CONFIGURACION_COMPLETA.md)** - Configuración paso a paso (ambos lados)
- [RESUMEN_EJECUTIVO.md](RESUMEN_EJECUTIVO.md) - Resumen del estado
- [SOLUCION_WEBHOOK.md](SOLUCION_WEBHOOK.md) - Guía detallada
- [ARQUITECTURA_WEBHOOK.md](ARQUITECTURA_WEBHOOK.md) - Diagrama y explicación

---

**Tiempo total:** ~5 minutos
**Dificultad:** Muy fácil ⭐
**Archivos modificados:** 1 (solo configuración)
