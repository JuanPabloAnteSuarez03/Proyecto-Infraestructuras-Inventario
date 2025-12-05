#!/bin/bash
# Script para configurar Tailscale en el servidor AWS
# Ejecutar en: ec2-98-93-67-35.compute-1.amazonaws.com

echo "=== Instalación de Tailscale en AWS ==="
echo ""

# 1. Instalar Tailscale
echo "1. Instalando Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh

# 2. Iniciar Tailscale
echo ""
echo "2. Iniciando Tailscale..."
echo "   IMPORTANTE: Copia el link que aparezca y ábrelo en tu navegador"
echo ""
sudo tailscale up

# 3. Obtener IP
echo ""
echo "3. Tu IP Tailscale de AWS:"
tailscale ip -4

# 4. Actualizar configuración
echo ""
echo "4. Actualizando configuración de fabricacion-api..."
cd fabricacion-api

# Backup
cp compose.yaml compose.yaml.backup

# Actualizar IP
sed -i 's|API_PATH_INVENTARIO:.*|API_PATH_INVENTARIO: http://100.70.143.89:5050/api/productos/ingresos|' compose.yaml

echo ""
echo "Cambio realizado:"
grep "API_PATH_INVENTARIO" compose.yaml

# 5. Reiniciar servicio
echo ""
echo "5. Reiniciando servicio..."
docker compose restart api

echo ""
echo "6. Verificando conectividad..."
sleep 3
curl -v http://100.70.143.89:5050/health

echo ""
echo "=== ✅ CONFIGURACIÓN COMPLETA ==="
echo ""
echo "Prueba final:"
echo "curl -X POST http://localhost:5050/api/fabricacion/ordenes \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"id_producto\": \"S1\", \"cantidad\": 50}'"
