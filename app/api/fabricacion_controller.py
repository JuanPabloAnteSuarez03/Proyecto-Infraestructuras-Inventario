import logging
from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
import os
from sqlalchemy.orm import Session
from ..services import (
    FabricacionService,
    InventarioProductosService,
    OrdenesFabricacionService,
    ProveedoresService,
    EntregasFabricacionService,
    FabricacionOrchestrator,
)
from ..models.entities import OrdenFabricacion
from ..repositories import InventarioPiezasRepository
from ..schemas.api_models import SolicitudFabricacion, CalculoPiezas, OrdenFabricacionAsync
from ..database import get_db
from ..utils.url_validator import URLValidationError

router = APIRouter(prefix="/api/fabricacion", tags=["fabricacion"])
fabricacion_service = FabricacionService()
logger = logging.getLogger(__name__)


@router.get("/plan/{codigo}")
def obtener_plan(
    codigo: str, cantidad: int = 1, session: Session = Depends(get_db)
):
    piezas_repository = InventarioPiezasRepository(session)
    if cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a cero")
    try:
        plan = fabricacion_service.solicitar_plan(codigo, cantidad)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    inventario_piezas = {
        pieza.id_pieza: pieza.cantidad for pieza in piezas_repository.get_all()
    }
    materiales = []
    for item in plan.materiales:
        materiales.append(
            {
                "id_pieza": item["id_pieza"],
                "cantidad_requerida": item["cantidad"],
                "cantidad_disponible": inventario_piezas.get(item["id_pieza"], 0),
            }
        )
    return {
        "id_producto": codigo.upper(),
        "cantidad_solicitada": cantidad,
        "materiales": materiales,
        "tiempo_estimado": plan.tiempo_produccion,
        "fuente_datos": getattr(plan, "fuente_datos", "interno"),
    }


@router.post("/calcular_piezas")
def calcular_piezas(body: CalculoPiezas):
    payload = body.model_dump()
    if payload["cantidad"] <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a cero")
    codigo = payload["codigo"].upper()
    try:
        base_plan = fabricacion_service.obtener_plan_base(codigo)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    piezas = []
    for pieza in base_plan["piezas"]:
        piezas.append(
            {
                "codigo": pieza["id_pieza"],
                "cantidad_por_unidad": pieza["cantidad"],
                "cantidad_total": pieza["cantidad"] * payload["cantidad"],
            }
        )

    return {
        "codigo": codigo,
        "cantidad_solicitada": payload["cantidad"],
        "piezas": piezas,
    }


@router.post("/producciones")
def producir_lote(body: SolicitudFabricacion, session: Session = Depends(get_db)):
    payload = body.model_dump()
    if payload["cantidad"] <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a cero")
    try:
        productos_service = InventarioProductosService(session)
        resultado = productos_service.fabricar_productos(
            producto_id=payload["id_producto"], cantidad=payload["cantidad"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return resultado


@router.post("/ordenes", status_code=202)
def crear_orden_fabricacion(
    body: OrdenFabricacionAsync, session: Session = Depends(get_db)
):
    payload = body.model_dump()
    codigo = payload["id_producto"].upper()
    cantidad = payload["cantidad"]

    orchestrator = FabricacionOrchestrator(session, fabricacion_service=fabricacion_service)
    try:
        resultado = orchestrator.crear_orden(codigo, cantidad)
        return resultado
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/ordenes/{orden_id}")
def obtener_orden_fabricacion(orden_id: int, session: Session = Depends(get_db)):
    ordenes_service = OrdenesFabricacionService(session)
    orden = ordenes_service.retrieve(orden_id)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return {
        "id": orden.id,
        "id_producto": orden.id_producto,
        "cantidad": orden.cantidad,
        "estado": orden.estado,
        "tiempo_estimado": orden.tiempo_estimado,
        "detalle": orden.detalle,
    }


@router.get("/ordenes")
def listar_ordenes_fabricacion(session: Session = Depends(get_db)):
    ordenes_service = OrdenesFabricacionService(session)
    ordenes = ordenes_service.list()
    return [
        {
            "id": o.id,
            "id_producto": o.id_producto,
            "cantidad": o.cantidad,
            "estado": o.estado,
            "tiempo_estimado": o.tiempo_estimado,
            "detalle": o.detalle,
        }
        for o in ordenes
    ]


@router.post("/ordenes/reset")
def resetear_ordenes(session: Session = Depends(get_db)):
    ordenes_service = OrdenesFabricacionService(session)
    total = ordenes_service.delete_all()
    return {"message": "Órdenes de fabricación reseteadas", "registros": total}


@router.get("/external/status")
def verificar_servicio_externo():
    """Proxy endpoint para verificar el estado del servicio externo de fabricación"""
    base_urls = FabricacionService.candidate_base_urls()
    if not base_urls:
        return {"conectado": False, "base_url": None, "planos": {}}

    last_planos: dict = {}
    for base_url in base_urls:
        planos = {}
        for plano_id, codigo in [(1, "S1"), (2, "S2")]:
            try:
                resp = httpx.get(f"{base_url}/fabricacion/planos/{plano_id}", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    planos[codigo] = {
                        "disponible": True,
                        "tiempo_fabricacion": data.get("tiempo_fabricacion"),
                        "nombre": data.get("nombre"),
                    }
                else:
                    planos[codigo] = {"disponible": False}
            except Exception:
                planos[codigo] = {"disponible": False}

        last_planos = planos
        if any(p.get("disponible") for p in planos.values()):
            # Persistir la URL que sí respondió para que toda la app use la misma
            FabricacionService.set_base_url(base_url)
            return {
                "conectado": True,
                "base_url": base_url,
                "planos": planos,
            }

    return {
        "conectado": False,
        "base_url": base_urls[0],
        "planos": last_planos,
    }


@router.get("/external/config")
def obtener_config_externa():
    """Ver configuración actual de fábrica externa."""
    base_url = FabricacionService.get_base_url()
    return {"base_url": base_url}


@router.post("/external/config")
def actualizar_config_externa(payload: dict):
    """
    Actualizar base_url de fábrica externa en caliente.

    Request body:
        {"base_url": "http://host.docker.internal:8555"}

    Returns:
        {"message": "...", "base_url": "..."}

    Raises:
        HTTPException 400: Si la URL es malformada o inválida
    """
    nueva_url = (payload or {}).get("base_url", "")

    try:
        # Validation happens inside set_base_url
        FabricacionService.set_base_url(nueva_url)

        return {
            "message": "Base URL de fábrica actualizada correctamente",
            "base_url": FabricacionService.get_base_url() or None
        }
    except URLValidationError as e:
        # Return detailed validation error to client
        raise HTTPException(
            status_code=400,
            detail={
                "error": "URL de fabricación inválida",
                "message": e.message,
                "url_provided": e.url,
                "details": e.details,
            }
        )
    except Exception as e:
        logger.error(f"Error al actualizar URL de fabricación: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al actualizar URL: {str(e)}"
        )


@router.get("/external/planos/{plano_id}")
def obtener_plano_externo(plano_id: int):
    """Proxy endpoint para obtener información de un plano del servicio externo"""
    bases = FabricacionService.candidate_base_urls()
    base_url = bases[0] if bases else ""
    if not base_url:
        raise HTTPException(status_code=503, detail="Servicio externo no configurado")

    try:
        resp = httpx.get(f"{base_url}/fabricacion/planos/{plano_id}", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail="Plano no encontrado en servicio externo"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Servicio externo no disponible: {str(exc)}"
        )


@router.post("/webhook/productos_terminados")
async def recibir_productos_fabricados(
    request: Request, session: Session = Depends(get_db)
):
    """
    Webhook para que la fábrica externa notifique productos terminados.

    Expected body:
    {
        "codigo": "S1",
        "cantidad": 1500,
        "estado": "Disponible"  # opcional, default: "Disponible"
    }
    """
    try:
        body = await request.json()
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("[WEBHOOK] Error parseando JSON: %s", exc)
        raise HTTPException(status_code=400, detail=f"JSON inválido: {str(exc)}")

    logger.info("[WEBHOOK] Recibido: %s", body)

    # Aceptar tanto "codigo" como "id_producto" y mapear alias numéricos
    raw_codigo = body.get("codigo") or body.get("id_producto")
    cantidad = body.get("cantidad")
    estado = body.get("estado", "Disponible")

    if not raw_codigo or not cantidad:
        raise HTTPException(
            status_code=400, detail="Se requieren 'codigo' y 'cantidad'"
        )

    codigo_alias = {"1": "S1", "2": "S2"}
    codigo = codigo_alias.get(str(raw_codigo).strip(), str(raw_codigo)).upper()

    try:
        productos_service = InventarioProductosService(session)
        producto = productos_service.incrementar(
            producto_id=codigo, cantidad=cantidad, estado=estado
        )

        entregas = EntregasFabricacionService(session).registrar_entrega(
            codigo=codigo,
            cantidad=cantidad,
            estados_objetivo=("esperando_fabricacion",),
        )

        return {
            "status": "ok",
            "mensaje": f"Recibidos {cantidad} productos {codigo}",
            "inventario_actual": producto.cantidad,
            "entrega": {
                "orden_id": entregas["orden"].id if entregas else None,
                "acumulado": entregas["acumulado"] if entregas else cantidad,
                "completada": bool(entregas and entregas["completada"]),
            },
        }
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(
            status_code=500, detail=f"Error procesando productos: {str(exc)}"
        )
