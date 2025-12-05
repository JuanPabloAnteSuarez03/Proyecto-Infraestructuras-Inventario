from __future__ import annotations
import os
import time
import redis
import psycopg
from rq import Queue
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from app.database import SessionLocal, DATABASE_URL
from app.services import (
    SolicitudesPiezaService,
    ProveedoresService,
    InventarioPiezasService,
    OrdenesFabricacionService,
    FabricacionService,
)
from app.repositories import InventarioPiezasRepository

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_conn = redis.from_url(redis_url)
queue = Queue(connection=redis_conn)

# Fallback de sesión para evitar errores de autenticación desde el worker
_fallback_session: sessionmaker | None = None


def _ensure_session():
    """Obtiene una sesión, con fallback a conexión directa psycopg si falla la estándar."""
    global _fallback_session
    try:
        return SessionLocal()
    except OperationalError:
        if _fallback_session is None:
            conn_url = make_url(DATABASE_URL)
            # psycopg.connect no entiende el sufijo +psycopg, lo removemos
            if conn_url.drivername.endswith("+psycopg"):
                conn_url = conn_url.set(drivername="postgresql")
            def _creator():
                return psycopg.connect(conn_url.render_as_string(hide_password=False))
            fallback_engine = create_engine(
                conn_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                creator=_creator,
            )
            _fallback_session = sessionmaker(
                autocommit=False, autoflush=False, bind=fallback_engine
            )
        return _fallback_session()


def procesar_solicitud_pieza(solicitud_id: int) -> None:
    session = _ensure_session()
    try:
        solicitudes_service = SolicitudesPiezaService(session)
        proveedores_service = ProveedoresService(session)
        piezas_service = InventarioPiezasService(session)

        solicitud = solicitudes_service.retrieve(solicitud_id)
        if not solicitud:
            return
        solicitud.estado = "en_proceso"
        session.commit()

        pieza = piezas_service.retrieve(solicitud.id_pieza)
        proveedor = proveedores_service.retrieve(pieza.id_proveedor) if pieza else None
        tiempo = proveedor.tiempo if proveedor else 0
        solicitud.tiempo_estimado = tiempo
        session.commit()

        time.sleep(min(tiempo, 1))

        pieza = piezas_service.retrieve(solicitud.id_pieza)
        if pieza:
            pieza.cantidad += solicitud.cantidad
        solicitud.estado = "completada"
        session.commit()
    finally:
        session.close()


def procesar_orden_fabricacion(orden_id: int) -> None:
    session = _ensure_session()
    try:
        ordenes_service = OrdenesFabricacionService(session)
        fabricacion_service = FabricacionService()
        piezas_repo = InventarioPiezasRepository(session)
        orden = ordenes_service.retrieve(orden_id)
        if not orden:
            return

        print(f"[WORKER] Procesando orden #{orden_id}: {orden.id_producto} x{orden.cantidad}")

        # Si la orden ya fue confirmada con fábrica externa
        if orden.estado == "confirmado":
            print(f"[WORKER] ✓ Orden #{orden_id} ya confirmada con fábrica externa")
            orden.estado = "consumiendo_piezas"
            session.commit()

            plan = fabricacion_service.solicitar_plan(orden.id_producto, orden.cantidad)
            print(f"[WORKER DEBUG] Plan materiales: {plan.materiales}")

            for material in plan.materiales:
                print(f"[WORKER DEBUG] Procesando material: {material}")
                pieza = piezas_repo.get_by_id(material["id_pieza"])
                print(f"[WORKER DEBUG] Pieza encontrada: {pieza}")
                if pieza:
                    print(f"[WORKER DEBUG] Cantidad antes: {pieza.cantidad}")
                    pieza.cantidad -= material["cantidad"]
                    print(f"[WORKER] Consumido {material['cantidad']} x {material['id_pieza']}")
                    print(f"[WORKER DEBUG] Cantidad después: {pieza.cantidad}")
                else:
                    print(f"[WORKER DEBUG] ⚠️ Pieza {material['id_pieza']} no encontrada en DB")

            session.commit()

            orden.estado = "esperando_fabricacion"
            session.commit()
            print(f"[WORKER] 📤 Piezas consumidas. Esperando productos de fábrica externa")
            print(f"[WORKER] ⏳ Fábrica debe llamar POST /api/fabricacion/webhook/productos_terminados")
            return

        # Si la orden ya está en progreso o completada, no marcar fallo: solo informar.
        if orden.estado in ("consumiendo_piezas", "esperando_fabricacion", "completada"):
            print(f"[WORKER] ℹ️ Orden #{orden_id} ya en estado '{orden.estado}'. No se modifica.")
            return

        if orden.estado == "confirmacion_fallida":
            print(f"[WORKER] ✗ Orden #{orden_id} sin confirmación externa - FALLIDA")
            print(f"[WORKER] No se permite fabricación local, solo externa")
            orden.estado = "fallida"
            if isinstance(orden.detalle, dict):
                orden.detalle["error"] = "Servicio externo no disponible. No se permite fabricación local."
            else:
                orden.detalle = {"error": "Servicio externo no disponible. No se permite fabricación local."}
            session.commit()
            return

        print(f"[WORKER] ⚠️ Orden #{orden_id} en estado inesperado: {orden.estado}")
        print(f"[WORKER] Estados esperados: 'confirmado' o 'confirmacion_fallida'")
        orden.estado = "fallida"
        if isinstance(orden.detalle, dict):
            orden.detalle["error"] = f"Estado inesperado: {orden.estado}. No se procesó la orden."
        else:
            orden.detalle = {"error": f"Estado inesperado: {orden.estado}. No se procesó la orden."}
        session.commit()
        print(f"[WORKER] Orden #{orden_id} marcada como fallida por estado inesperado")
    except Exception as exc:  # pylint: disable=broad-except
        orden = locals().get("orden")
        if orden:
            orden.estado = "fallida"
            if isinstance(orden.detalle, dict):
                orden.detalle["error"] = str(exc)
            else:
                orden.detalle = {"error": str(exc)}
            session.commit()
        print(f"[WORKER] ✗ Orden #{orden_id} falló: {exc}")
    finally:
        session.close()
