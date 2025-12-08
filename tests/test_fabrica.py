#!/usr/bin/env python3
"""
Script de prueba para la API de fabricación externa.
Ejecutar: python test_fabrica.py
"""
import httpx
import json
import os
from datetime import datetime

# URL de la fábrica
FABRICA_URL = os.getenv("FABRICA_URL", "http://localhost:8555")

# URL de tu API local
LOCAL_URL = os.getenv("LOCAL_URL", "http://localhost:5050")


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_section(text):
    print(f"\n{'-'*60}")
    print(f"{text}")
    print(f"{'-'*60}")


def test_fabrica_externa():
    """Prueba la API de la fábrica externa"""
    print_header("PRUEBAS API FÁBRICA EXTERNA")

    # Test 1: Endpoint raíz
    print_section("1. Probando endpoint raíz")
    try:
        resp = httpx.get(FABRICA_URL, timeout=10)
        print(f"✓ Status: {resp.status_code}")
        print(f"✓ URL disponible: {FABRICA_URL}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Test 2: Documentación
    print_section("2. Documentación Swagger")
    print(f"   Abrir en navegador: {FABRICA_URL}/docs")

    # Test 3: Planos
    print_section("3. Consultar planos de fabricación")
    planos = {1: "S1", 2: "S2"}
    for plano_id, codigo in planos.items():
        try:
            resp = httpx.get(f"{FABRICA_URL}/fabricacion/planos/{plano_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                print(f"   ✓ Plano {codigo}:")
                print(f"      Nombre: {data.get('nombre', 'N/A')}")
                print(f"      Tiempo fabricación: {data.get('tiempo_fabricacion', 'N/A')} min")
                print(f"      Piezas: {json.dumps(data.get('piezas', []), indent=8)}")
            else:
                print(f"   ✗ Plano {codigo}: HTTP {resp.status_code}")
        except Exception as e:
            print(f"   ✗ Plano {codigo}: {e}")

    # Test 4: Cálculo de piezas
    print_section("4. Calcular piezas necesarias")
    test_cases = [
        {"codigo": "1", "cantidad": 100},
        {"codigo": "S2", "cantidad": 200},
    ]

    for test_case in test_cases:
        try:
            resp = httpx.post(
                f"{FABRICA_URL}/fabricacion/calculo_piezas",
                json=test_case,
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                print(f"   ✓ {test_case['codigo']} x {test_case['cantidad']}:")
                for pieza in data.get("piezas", []):
                    print(f"      - {pieza.get('codigo_pieza')}: {pieza.get('total_piezas')} unidades")
            else:
                print(f"   ✗ {test_case['codigo']}: HTTP {resp.status_code}")
                print(f"      {resp.text}")
        except Exception as e:
            print(f"   ✗ {test_case['codigo']}: {e}")

    return True


def test_api_local():
    """Prueba la API local de inventarios"""
    print_header("PRUEBAS API LOCAL")

    # Test 1: Health check
    print_section("1. Verificar API local")
    try:
        resp = httpx.get(f"{LOCAL_URL}/health", timeout=5)
        print(f"✓ API local respondiendo: {resp.status_code}")
    except Exception as e:
        print(f"✗ API local no disponible: {e}")
        print(f"   Asegúrate de ejecutar: sudo docker compose up -d")
        return False

    # Test 2: Verificar conexión con fábrica externa
    print_section("2. Estado de conexión con fábrica externa")
    try:
        resp = httpx.get(f"{LOCAL_URL}/api/fabricacion/external/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"   Conectado: {data.get('conectado')}")
            print(f"   URL: {data.get('base_url')}")
            print(f"   Planos disponibles:")
            for codigo, info in data.get('planos', {}).items():
                print(f"      - {codigo}: {info}")
        else:
            print(f"✗ Error: HTTP {resp.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 3: Obtener plan de fabricación
    print_section("3. Obtener plan de fabricación (S1, cantidad=100)")
    try:
        resp = httpx.get(
            f"{LOCAL_URL}/api/fabricacion/plan/S1",
            params={"cantidad": 100},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✓ Plan obtenido:")
            print(f"      Producto: {data.get('id_producto')}")
            print(f"      Cantidad: {data.get('cantidad_solicitada')}")
            print(f"      Tiempo estimado: {data.get('tiempo_estimado')} min")
            print(f"      Materiales:")
            for mat in data.get('materiales', []):
                print(f"         - {mat['id_pieza']}: {mat['cantidad_requerida']} requeridas, "
                      f"{mat['cantidad_disponible']} disponibles")
        else:
            print(f"✗ Error: HTTP {resp.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")

    return True


def main():
    print(f"\n{'#'*60}")
    print(f"  SCRIPT DE PRUEBAS - API FABRICACIÓN")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # Probar fábrica externa
    fabrica_ok = test_fabrica_externa()

    # Probar API local si está disponible
    if fabrica_ok:
        test_api_local()

    print_header("RESUMEN")
    print("""
Endpoints disponibles en tu API local:

Fabricación:
  - GET  /api/fabricacion/plan/{codigo}?cantidad=X
  - POST /api/fabricacion/ordenes
  - GET  /api/fabricacion/ordenes
  - GET  /api/fabricacion/ordenes/{id}
  - GET  /api/fabricacion/external/status
  - GET  /api/fabricacion/external/planos/{id}

Inventario:
  - GET  /api/inventario/productos
  - GET  /api/inventario/piezas

Proveedores:
  - GET  /api/proveedores
  - POST /api/proveedores/solicitar

Webhook (para fábrica externa):
  - POST /api/fabricacion/webhook/productos_terminados

Documentación local:
  - http://localhost:5050/docs
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nPruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"\n\nError inesperado: {e}")
