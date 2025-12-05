from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..schemas.api_models import (
    ProveedorCreate,
    ProveedorUpdate,
    SolicitudPiezas,
    SolicitudPiezaAsync,
)
from ..database import get_db
from ..services import ProveedoresService, SolicitudesPiezaService
from ..tasks import queue, procesar_solicitud_pieza

router = APIRouter(prefix="/api/proveedores", tags=["proveedores"])


def serialize_proveedor(p):
    return {
        "id_proveedor": p.id_proveedor,
        "nombre": p.nombre,
        "cantidad": p.cantidad,
        "tiempo": p.tiempo,
    }


@router.get("")
def listar_proveedores(db: Session = Depends(get_db)):
    service = ProveedoresService(db)
    proveedores = service.list()
    return [serialize_proveedor(p) for p in proveedores]


@router.post("", status_code=201)
def crear_proveedor(body: ProveedorCreate, db: Session = Depends(get_db)):
    service = ProveedoresService(db)
    payload = body.model_dump()
    proveedor = service.create(payload)
    return serialize_proveedor(proveedor)


@router.delete("/{proveedor_id}")
def eliminar_proveedor(proveedor_id: int, db: Session = Depends(get_db)):
    service = ProveedoresService(db)
    eliminado = service.delete(proveedor_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return {"message": "Proveedor eliminado"}


@router.put("/{proveedor_id}")
def actualizar_proveedor(
    proveedor_id: int, body: ProveedorUpdate, db: Session = Depends(get_db)
):
    service = ProveedoresService(db)
    payload = body.model_dump(exclude_unset=True)
    payload.pop("id_proveedor", None)
    proveedor = service.update(proveedor_id, payload)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return serialize_proveedor(proveedor)


@router.post("/solicitudes")
def solicitar_piezas(body: SolicitudPiezas, db: Session = Depends(get_db)):
    service = ProveedoresService(db)
    payload = body.model_dump()
    try:
        resultado = service.solicitar_piezas(
            pieza_id=payload["id_pieza"], cantidad=payload["cantidad"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return resultado


@router.post("/solicitudes_async", status_code=202)
def solicitar_piezas_async(body: SolicitudPiezaAsync, db: Session = Depends(get_db)):
    solicitudes_service = SolicitudesPiezaService(db)
    payload = body.model_dump()
    solicitud = solicitudes_service.create(
        {"id_pieza": payload["id_pieza"], "cantidad": payload["cantidad"], "estado": "pendiente"}
    )
    queue.enqueue(procesar_solicitud_pieza, solicitud.id)
    return {
        "id": solicitud.id,
        "estado": solicitud.estado,
        "tiempo_estimado": solicitud.tiempo_estimado,
    }


@router.get("/solicitudes_async/{solicitud_id}")
def obtener_solicitud_async(solicitud_id: int, db: Session = Depends(get_db)):
    solicitudes_service = SolicitudesPiezaService(db)
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
def listar_solicitudes_async(db: Session = Depends(get_db)):
    solicitudes_service = SolicitudesPiezaService(db)
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


@router.post("/solicitudes_async/reset")
def resetear_solicitudes_async(db: Session = Depends(get_db)):
    solicitudes_service = SolicitudesPiezaService(db)
    total = solicitudes_service.delete_all()
    return {"message": "Solicitudes async reseteadas", "registros": total}


@router.get("/{proveedor_id}")
def obtener_proveedor(proveedor_id: int, db: Session = Depends(get_db)):
    service = ProveedoresService(db)
    proveedor = service.retrieve(proveedor_id)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return serialize_proveedor(proveedor)
