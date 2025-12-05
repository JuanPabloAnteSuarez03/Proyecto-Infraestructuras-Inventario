# app/main.py
from fastapi import FastAPI
from app.api.rutas_fabricacion import router as fabricacion_router
from contextlib import asynccontextmanager
import asyncio
from app.utils.fabricacion_workers import consumer_fabricacion

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(consumer_fabricacion())
    yield

app = FastAPI(title="Servicio de Fabricación",
              lifespan=lifespan)

# Registrar las rutas específicas de fabricación
app.include_router(fabricacion_router)



@app.get("/health")
def health_check():
    """
    Endpoint simple para comprobar que el servicio está vivo.
    """
    return {"status": "ok", "service": "fabricacion"}
