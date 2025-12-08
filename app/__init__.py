import os
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .routes import register_routes
from .database import Base, engine, SessionLocal
from .core.logging_config import setup_logging
from .services import (
    InventarioProductosService,
    OrdenesFabricacionService,
    InventarioPiezasService,
    ProveedoresService,
    SolicitudesPiezaService,
)


def create_app(config_name: str | None = None) -> FastAPI:
    """Factory FastAPI con SQLAlchemy puro (sin Flask)."""
    env_config = (
        config_name
        or os.getenv("APP_ENV")
        or os.getenv("FLASK_ENV")  # compat con variables antiguas
        or "development"
    )

    setup_logging()

    async def _auto_restock_loop(interval: int = 30, piezas_interval: int = 30) -> None:
        """
        Loop sencillo que revisa stock disponible y encola órdenes de reposición
        cuando se cae bajo el mínimo, sin depender de reservas/ despachos.
        """
        log = logging.getLogger("auto_restock")
        while True:
            await asyncio.sleep(interval)
            try:
                with SessionLocal() as session:
                    _verificar_productos(session, log)
                    _verificar_piezas(session, log)
            except Exception as exc:  # pylint: disable=broad-except
                log.warning("[AUTO_STOCK] Error en loop de reposición: %s", exc)

    def _orden_en_curso(ordenes_service: OrdenesFabricacionService, codigo: str) -> bool:
        """Evita duplicar órdenes si ya hay una activa para el mismo producto."""
        activos = (
            o
            for o in ordenes_service.list()
            if o.id_producto == codigo
            and o.estado not in ("completada", "fallida", "confirmacion_fallida")
        )
        return any(activos)

    def _verificar_productos(session, log) -> None:
        productos_service = InventarioProductosService(session)
        ordenes_service = OrdenesFabricacionService(session)
        codigos = {p.id_producto for p in productos_service.list()}
        for codigo in codigos:
            info = productos_service._evaluar_stock_minimo(codigo)
            if info.get("accion") != "fabricar":
                continue
            if _orden_en_curso(ordenes_service, codigo):
                log.debug(
                    "[AUTO_STOCK] Reposición ya en curso para %s; se omite encolado",
                    codigo,
                )
                continue
            productos_service._encolar_reposicion(
                codigo, info.get("cantidad_reponer", 0)
            )
            log.info(
                "[AUTO_STOCK] Reposición automática encolada: %s x%s",
                codigo,
                info.get("cantidad_reponer", 0),
            )

    def _verificar_piezas(session, log) -> None:
        """
        Reabastece piezas cuando bajan del mínimo configurado.
        Solicita a proveedores y marca solicitudes para que aparezcan en dashboard.
        """
        piezas_service = InventarioPiezasService(session)
        proveedores_service = ProveedoresService(session, piezas_repository=piezas_service.repository)
        solicitudes_service = SolicitudesPiezaService(session)

        stock_min = int(os.getenv("PIEZAS_STOCK_MINIMO", "100"))
        stock_obj = int(os.getenv("PIEZAS_STOCK_OBJETIVO", "300"))

        piezas = piezas_service.list()
        for pieza in piezas:
            if pieza.cantidad >= stock_min:
                continue
            # Evitar duplicados si ya hay solicitud en proceso para esta pieza
            pendientes = [
                s for s in solicitudes_service.list()
                if s.id_pieza == pieza.id_pieza and s.estado == "en_proceso"
            ]
            if pendientes:
                continue
            cantidad_reponer = max(stock_obj - pieza.cantidad, 0)
            if cantidad_reponer <= 0:
                continue
            eta = pieza.proveedor.tiempo if pieza.proveedor else 0
            solicitud = solicitudes_service.create(
                {
                    "id_pieza": pieza.id_pieza,
                    "cantidad": cantidad_reponer,
                    "estado": "en_proceso",
                    "tiempo_estimado": eta,
                }
            )
            res = proveedores_service.solicitar_piezas(pieza.id_pieza, cantidad_reponer)
            tiempo_entrega = res.get("tiempo_entrega", eta) if isinstance(res, dict) else eta
            solicitudes_service.update(
                solicitud.id,
                {"estado": "completada", "tiempo_estimado": tiempo_entrega},
            )
            log.info(
                "[AUTO_PIEZAS] Reposición pieza %s x%s (ETA %s min)",
                pieza.id_pieza,
                cantidad_reponer,
                tiempo_entrega,
            )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        Base.metadata.create_all(bind=engine)
        interval = int(os.getenv("AUTO_RESTOCK_INTERVAL", "30"))
        piezas_interval = int(os.getenv("AUTO_PIEZAS_INTERVAL", str(interval)))
        restock_task = asyncio.create_task(_auto_restock_loop(interval, piezas_interval))
        try:
            yield
        finally:
            restock_task.cancel()
            with suppress(asyncio.CancelledError):
                await restock_task

    app = FastAPI(title="API Inventarios", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routes(app)

    @app.get("/health")
    def healthcheck():
        return {"status": "ok", "environment": env_config}

    @app.exception_handler(HTTPException)
    def http_exception_handler(_, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    @app.exception_handler(Exception)
    def unhandled_exception_handler(_, exc: Exception):
        return JSONResponse(
            status_code=500, content={"error": "Error interno del servidor"}
        )

    return app
