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
from app.models import InventarioPieza

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
        proveedores_service = ProveedoresService(session, piezas_repository=InventarioPiezasRepository(session))
        orden = ordenes_service.retrieve(orden_id)
        if not orden:
            return

        print(f"[WORKER] Procesando orden #{orden_id}: {orden.id_producto} x{orden.cantidad}")

        detalle_orden = orden.detalle if isinstance(orden.detalle, dict) else {}
        detalle_orden.setdefault("solicitudes_piezas", [])
        detalle_orden.setdefault("consumo_piezas", [])
        piezas_solicitadas = {s.get("id_pieza") for s in detalle_orden["solicitudes_piezas"] if isinstance(s, dict)}
        if detalle_orden.get("consumido_en_orquestador"):
            print(f"[WORKER] ℹ️ Orden #{orden_id} ya consumió piezas en el orquestador; se omite en worker.")
            orden.estado = "esperando_fabricacion"
            orden.detalle = detalle_orden
            session.commit()
            return

        # Procesar órdenes confirmadas o en reabastecimiento
        if orden.estado not in ("confirmado", "reabasteciendo", "consumiendo_piezas"):
            print(f"[WORKER] ℹ️ Orden #{orden_id} en estado '{orden.estado}', se espera 'confirmado/reabasteciendo'. No se consume.")
            return

        orden.estado = "consumiendo_piezas"
        session.commit()

        plan_base = fabricacion_service.obtener_plan_base(orden.id_producto)
        materiales_plan = [
            {"id_pieza": item["id_pieza"], "cantidad": item["cantidad"] * orden.cantidad}
            for item in plan_base.get("piezas", [])
        ]
        print(f"[WORKER DEBUG] Plan materiales (interno): {materiales_plan}")

        # Pausa breve para permitir que el dashboard muestre el reabastecimiento antes del consumo
        time.sleep(1.0)

        for material in materiales_plan:
            print(f"[WORKER DEBUG] Procesando material: {material}")
            pieza = (
                session.query(InventarioPieza)
                .filter_by(id_pieza=material["id_pieza"])
                .with_for_update()
                .first()
            )
            if not pieza:
                print(f"[WORKER DEBUG] ⚠️ Pieza {material['id_pieza']} no encontrada en DB")
                continue

            print(f"[WORKER DEBUG] Cantidad antes: {pieza.cantidad}")
            requerido = material["cantidad"]

            if pieza.cantidad < requerido and material["id_pieza"] not in piezas_solicitadas:
                faltante = requerido - pieza.cantidad
                print(f"[WORKER] ⚠️ Stock insuficiente de {material['id_pieza']} (faltan {faltante}), solicitando a proveedor")
                res = proveedores_service.solicitar_piezas(material["id_pieza"], faltante)
                detalle_orden["solicitudes_piezas"].append(
                    {
                        "id_pieza": material["id_pieza"],
                        "cantidad": faltante,
                        "tiempo_entrega": res.get("tiempo_entrega", 0) if isinstance(res, dict) else 0,
                    }
                )
                piezas_solicitadas.add(material["id_pieza"])
                session.refresh(pieza)
                print(f"[WORKER DEBUG] Stock después de reabastecer: {pieza.cantidad}")

            consumo = min(pieza.cantidad, requerido)
            pieza.cantidad = max(pieza.cantidad - consumo, 0)
            session.commit()
            print(f"[WORKER] Consumido {consumo} x {material['id_pieza']}")
            print(f"[WORKER DEBUG] Cantidad después: {pieza.cantidad}")
            detalle_orden["consumo_piezas"].append(
                {
                    "id_pieza": material["id_pieza"],
                    "consumido": consumo,
                    "requerido": requerido,
                    "restante": pieza.cantidad,
                }
            )

        orden.estado = "esperando_fabricacion"
        orden.detalle = detalle_orden
        session.commit()
        print(f"[WORKER] 📤 Piezas consumidas. Esperando productos de fábrica externa")
        print(f"[WORKER] ⏳ Fábrica debe llamar POST /api/fabricacion/webhook/productos_terminados")
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
