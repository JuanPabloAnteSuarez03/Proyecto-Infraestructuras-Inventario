from fastapi import APIRouter, HTTPException
from marshmallow import ValidationError
from ..schemas.inventory import ProveedorSchema, SolicitudPiezasSchema
from ..schemas.api_models import (
    ProveedorCreate,
    ProveedorUpdate,
    SolicitudPiezas,
    SolicitudPiezaAsync,
)
from ..services.proveedores_service import ProveedoresService
from ..services import SolicitudesPiezaService
from ..tasks import queue, procesar_solicitud_pieza

router = APIRouter(prefix="/api/proveedores", tags=["proveedores"])
service = ProveedoresService()
solicitudes_service = SolicitudesPiezaService()
proveedor_schema = ProveedorSchema()
proveedores_schema = ProveedorSchema(many=True)
solicitud_piezas_schema = SolicitudPiezasSchema()


@router.get("")
def listar_proveedores():
    proveedores = service.list()
    return proveedores_schema.dump(proveedores)


@router.post("", status_code=201)
def crear_proveedor(body: ProveedorCreate):
    payload = body.model_dump()
    try:
        data = proveedor_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    proveedor = service.create(data)
    return proveedor_schema.dump(proveedor)


@router.delete("/{proveedor_id}")
def eliminar_proveedor(proveedor_id: int):
    eliminado = service.delete(proveedor_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return {"message": "Proveedor eliminado"}


@router.put("/{proveedor_id}")
def actualizar_proveedor(proveedor_id: int, body: ProveedorUpdate):
    payload = body.model_dump(exclude_unset=True)
    try:
        data = proveedor_schema.load(payload, partial=True)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    data.pop("id_proveedor", None)
    proveedor = service.update(proveedor_id, data)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return proveedor_schema.dump(proveedor)


@router.post("/solicitudes")
def solicitar_piezas(body: SolicitudPiezas):
    payload = body.model_dump()
    try:
        data = solicitud_piezas_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    try:
        resultado = service.solicitar_piezas(
            pieza_id=data["id_pieza"], cantidad=data["cantidad"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return resultado


@router.post("/solicitudes_async", status_code=202)
def solicitar_piezas_async(body: SolicitudPiezaAsync):
    payload = body.model_dump()
    try:
        data = solicitud_piezas_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    solicitud = solicitudes_service.create(
        {"id_pieza": data["id_pieza"], "cantidad": data["cantidad"], "estado": "pendiente"}
    )
    queue.enqueue(procesar_solicitud_pieza, solicitud.id)
    return {
        "id": solicitud.id,
        "estado": solicitud.estado,
        "tiempo_estimado": solicitud.tiempo_estimado,
    }


@router.get("/solicitudes_async/{solicitud_id}")
def obtener_solicitud_async(solicitud_id: int):
    solicitud = solicitudes_service.retrieve(solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return {
        "id": solicitud.id,
        "id_pieza": solicitud.id_pieza,
        "cantidad": solicitud.cantidad,
        "estado": solicitud.estado,
        "tiempo_estimado": solicitud.tiempo_estimado,
    }


@router.get("/solicitudes_async")
def listar_solicitudes_async():
    solicitudes = solicitudes_service.list()
    return [
        {
            "id": s.id,
            "id_pieza": s.id_pieza,
            "cantidad": s.cantidad,
            "estado": s.estado,
            "tiempo_estimado": s.tiempo_estimado,
        }
        for s in solicitudes
    ]


@router.get("/{proveedor_id}")
def obtener_proveedor(proveedor_id: int):
    proveedor = service.retrieve(proveedor_id)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return proveedor_schema.dump(proveedor)
