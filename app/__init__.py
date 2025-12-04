import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .routes import register_routes
from .database import Base, engine


def create_app(config_name: str | None = None) -> FastAPI:
    """Factory FastAPI con SQLAlchemy puro (sin Flask)."""
    env_config = config_name or os.getenv("FLASK_ENV", "development")

    app = FastAPI(title="API Inventarios", version="1.0.0")

    @app.on_event("startup")
    def _init_models() -> None:
        Base.metadata.create_all(bind=engine)

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
