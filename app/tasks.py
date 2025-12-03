from __future__ import annotations
import os
import time
import redis
from rq import Queue
from app.extensions import db


redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_conn = redis.from_url(redis_url)
queue = Queue(connection=redis_conn)
_APP = None


def get_app():
    global _APP  # pylint: disable=global-statement
    if _APP is None:
        from app import create_app

        _APP = create_app(os.getenv("FLASK_ENV", "development"))
    return _APP


def procesar_solicitud_pieza(solicitud_id: int) -> None:
    get_app()
    from app.services import (
        SolicitudesPiezaService,
        ProveedoresService,
        InventarioPiezasService,
    )

    solicitudes_service = SolicitudesPiezaService()
    proveedores_service = ProveedoresService()
    piezas_service = InventarioPiezasService()

    solicitud = solicitudes_service.retrieve(solicitud_id)
    if not solicitud:
        return
    solicitud.estado = "en_proceso"
    db.session.commit()

    pieza = piezas_service.retrieve(solicitud.id_pieza)
    proveedor = proveedores_service.retrieve(pieza.id_proveedor) if pieza else None
    tiempo = proveedor.tiempo if proveedor else 0
    solicitud.tiempo_estimado = tiempo
    db.session.commit()

    # Simulación de espera (capado a 1 segundo para no bloquear demasiado)
    time.sleep(min(tiempo, 1))

    pieza = piezas_service.retrieve(solicitud.id_pieza)
    if pieza:
        pieza.cantidad += solicitud.cantidad
    solicitud.estado = "completada"
    db.session.commit()


def procesar_orden_fabricacion(orden_id: int) -> None:
    get_app()
    from app.services import (
        OrdenesFabricacionService,
        InventarioProductosService,
        FabricacionService,
    )

    ordenes_service = OrdenesFabricacionService()
    productos_service = InventarioProductosService()
    fabricacion_service = FabricacionService()
    orden = ordenes_service.retrieve(orden_id)
    if not orden:
        return
    orden.estado = "en_proceso"
    db.session.commit()

    try:
        resultado = productos_service.fabricar_productos(
            producto_id=orden.id_producto, cantidad=orden.cantidad
        )
        orden.estado = "completada"
        orden.tiempo_estimado = resultado.get("tiempo_total", 0)
        orden.detalle = resultado
        db.session.commit()
    except Exception as exc:  # pylint: disable=broad-except
        orden.estado = "fallida"
        orden.detalle = {"error": str(exc)}
        db.session.commit()
