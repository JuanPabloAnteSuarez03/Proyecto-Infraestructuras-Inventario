from __future__ import annotations
import os
import time
import redis
from rq import Queue
from app.database import SessionLocal
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


def procesar_solicitud_pieza(solicitud_id: int) -> None:
    session = SessionLocal()
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
    session = SessionLocal()
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
