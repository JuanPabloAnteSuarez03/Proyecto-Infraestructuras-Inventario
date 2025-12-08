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
from .services import InventarioProductosService, OrdenesFabricacionService


def create_app(config_name: str | None = None) -> FastAPI:
    """Factory FastAPI con SQLAlchemy puro (sin Flask)."""
    env_config = (
        config_name
        or os.getenv("APP_ENV")
        or os.getenv("FLASK_ENV")  # compat con variables antiguas
        or "development"
    )

    setup_logging()

    async def _auto_restock_loop(interval: int = 30) -> None:
        """
        Loop sencillo que revisa stock disponible y encola órdenes de reposición
        cuando se cae bajo el mínimo, sin depender de reservas/ despachos.
        """
        log = logging.getLogger("auto_restock")
        while True:
            await asyncio.sleep(interval)
            try:
                with SessionLocal() as session:
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

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        Base.metadata.create_all(bind=engine)
        interval = int(os.getenv("AUTO_RESTOCK_INTERVAL", "30"))
        restock_task = asyncio.create_task(_auto_restock_loop(interval))
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
