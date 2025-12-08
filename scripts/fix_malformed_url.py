#!/usr/bin/env python3
"""
Emergency fix script to clear malformed fabrication URL from Redis.

Este script elimina URLs malformadas de Redis y restaura el sistema
a usar las URLs de fallback configuradas en .env

Usage: python scripts/fix_malformed_url.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.redis_client import get_redis
from app.services.fabricacion.fabricacion_service import FabricacionService


def main():
    """Limpiar URL malformada de Redis y mostrar configuración actual."""
    print("🔧 Limpiando URL malformada de fabricación desde Redis...")
    print()

    try:
        redis_client = get_redis()
        key = "fabricacion:base_url"

        # Check current value
        current = redis_client.get(key)
        if current:
            current_url = current.decode()
            print(f"📝 Valor actual en Redis: {current_url}")

            # Validate current URL
            from app.utils.url_validator import FabricationURLValidator, URLValidationError
            try:
                FabricationURLValidator.validate(current_url, allow_empty=False)
                print("   ✅ La URL actual es válida")
                print()
                print("⚠️  No se requiere limpieza. La URL en Redis es correcta.")
                return
            except URLValidationError as e:
                print(f"   ❌ URL inválida detectada: {e.message}")
                print()
        else:
            print("ℹ️  No hay valor almacenado actualmente en Redis")
            print()

        # Delete the key
        result = redis_client.delete(key)
        if result > 0:
            print(f"✅ Eliminada clave de Redis: {key}")
        else:
            print(f"ℹ️  La clave {key} no existía en Redis")

        print()
        print("📋 Cadena de fallback actual (URLs que se intentarán en orden):")
        for idx, url in enumerate(FabricacionService.candidate_base_urls(), 1):
            print(f"   {idx}. {url}")

        print()
        print("✅ Limpieza completa! El sistema ahora usará las URLs de fallback.")
        print()
        print("📌 Próximos pasos:")
        print("   1. Verificar que el servicio externo está corriendo en uno de los puertos listados")
        print("   2. Actualizar la URL correcta desde el dashboard si es necesario")
        print("   3. Usar el formato correcto: http://host.docker.internal:8555")

    except Exception as e:
        print(f"❌ Error al limpiar Redis: {e}")
        print()
        print("💡 Posibles causas:")
        print("   - Redis no está corriendo")
        print("   - Variables de entorno de conexión incorrectas")
        print("   - Permisos insuficientes")
        sys.exit(1)


if __name__ == "__main__":
    main()
