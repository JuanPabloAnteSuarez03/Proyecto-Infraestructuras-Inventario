from fastapi import APIRouter, HTTPException
from marshmallow import ValidationError
from ..services import (
    FabricacionService,
    InventarioProductosService,
    OrdenesFabricacionService,
)
from ..repositories import InventarioPiezasRepository
from ..schemas.inventory import SolicitudFabricacionSchema, SolicitudCalculoPiezasSchema
from ..schemas.api_models import SolicitudFabricacion, CalculoPiezas, OrdenFabricacionAsync
from ..tasks import queue, procesar_orden_fabricacion

router = APIRouter(prefix="/api/fabricacion", tags=["fabricacion"])
fabricacion_service = FabricacionService()
productos_service = InventarioProductosService()
piezas_repository = InventarioPiezasRepository()
ordenes_service = OrdenesFabricacionService()
piezas_repository = InventarioPiezasRepository()
solicitud_schema = SolicitudFabricacionSchema()
calculo_schema = SolicitudCalculoPiezasSchema()


@router.get("/plan/{codigo}")
def obtener_plan(codigo: str, cantidad: int = 1):
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
    }


@router.post("/calcular_piezas")
def calcular_piezas(body: CalculoPiezas):
    payload = body.model_dump()
    try:
        data = calculo_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    codigo = data["codigo"].upper()
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
                "cantidad_total": pieza["cantidad"] * data["cantidad"],
            }
        )

    return {
        "codigo": codigo,
        "cantidad_solicitada": data["cantidad"],
        "piezas": piezas,
    }


@router.post("/producciones")
def producir_lote(body: SolicitudFabricacion):
    payload = body.model_dump()
    try:
        data = solicitud_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    try:
        resultado = productos_service.fabricar_productos(
            producto_id=data["id_producto"], cantidad=data["cantidad"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return resultado


@router.post("/ordenes", status_code=202)
def crear_orden_fabricacion(body: OrdenFabricacionAsync):
    payload = body.model_dump()
    orden = ordenes_service.create(
        {"id_producto": payload["id_producto"], "cantidad": payload["cantidad"], "estado": "pendiente"}
    )
    queue.enqueue(procesar_orden_fabricacion, orden.id)
    return {"id": orden.id, "estado": orden.estado, "tiempo_estimado": orden.tiempo_estimado}


@router.get("/ordenes/{orden_id}")
def obtener_orden_fabricacion(orden_id: int):
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
def listar_ordenes_fabricacion():
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
