#!/bin/bash
# Script para probar el flujo completo manualmente

echo "=== PRUEBA MANUAL DE INTEGRACIÓN ==="
echo ""

echo "1️⃣ Creando orden de fabricación..."
ORDER_RESPONSE=$(curl -s -X POST http://localhost:5050/api/fabricacion/ordenes \
  -H "Content-Type: application/json" \
  -d '{"id_producto": "S1", "cantidad": 50}')

echo "$ORDER_RESPONSE" | python -m json.tool

ORDER_ID=$(echo "$ORDER_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin).get('id', 'N/A'))")
echo ""
echo "Orden creada: #$ORDER_ID"
echo ""

echo "2️⃣ Esperando 5 segundos (simulando fabricación)..."
sleep 5
echo ""

echo "3️⃣ Simulando webhook de fábrica (productos terminados)..."
WEBHOOK_RESPONSE=$(curl -s -X POST http://localhost:5050/api/productos/ingresos \
  -H "Content-Type: application/json" \
  -d '{"codigo": "S1", "cantidad": 50}')

echo "$WEBHOOK_RESPONSE" | python -m json.tool
echo ""

echo "4️⃣ Verificando estado de la orden..."
curl -s http://localhost:5050/api/fabricacion/ordenes/$ORDER_ID | python -m json.tool
echo ""

echo "5️⃣ Verificando inventario actualizado..."
curl -s http://localhost:5050/api/productos | python -m json.tool | grep -A3 '"id_producto": "S1"'
echo ""

echo "=== ✅ PRUEBA COMPLETA ==="
