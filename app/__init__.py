import os
from flask import Flask
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .config import get_config
from .extensions import db, ma
from .routes import register_routes


def _init_flask_context(config_name: str) -> Flask:
    flask_app = Flask(__name__)
    flask_app.config.from_object(get_config(config_name))
    db.init_app(flask_app)
    ma.init_app(flask_app)
    flask_app.app_context().push()
    return flask_app


def create_app(config_name: str | None = None) -> FastAPI:
    """Factory que crea la app FastAPI reutilizando el contexto de Flask para SQLAlchemy/Marshmallow."""
    env_config = config_name or os.getenv("FLASK_ENV", "development")
    _init_flask_context(env_config)

    app = FastAPI(title="API Inventarios", version="1.0.0")

    @app.middleware("http")
    async def db_session_middleware(request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        finally:
            db.session.remove()

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
