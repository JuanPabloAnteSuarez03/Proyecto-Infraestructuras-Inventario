from fastapi import APIRouter, HTTPException
from marshmallow import ValidationError
from ..schemas.inventory import MovimientoSchema
from ..schemas.api_models import MovimientoCreate, MovimientoUpdate
from ..services.movimientos_service import MovimientosService

router = APIRouter(prefix="/api/movimientos", tags=["movimientos"])
service = MovimientosService()
movimiento_schema = MovimientoSchema()
movimientos_schema = MovimientoSchema(many=True)


@router.get("")
def listar_movimientos():
    movimientos = service.list()
    return movimientos_schema.dump(movimientos)


@router.get("/{movimiento_id}")
def obtener_movimiento(movimiento_id: int):
    movimiento = service.retrieve(movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return movimiento_schema.dump(movimiento)


@router.post("", status_code=201)
def crear_movimiento(body: MovimientoCreate):
    payload = body.model_dump()
    try:
        data = movimiento_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    movimiento = service.create(data)
    return movimiento_schema.dump(movimiento)


@router.delete("/{movimiento_id}")
def eliminar_movimiento(movimiento_id: int):
    eliminado = service.delete(movimiento_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return {"message": "Movimiento eliminado"}


@router.put("/{movimiento_id}")
def actualizar_movimiento(movimiento_id: int, body: MovimientoUpdate):
    payload = body.model_dump(exclude_unset=True)
    try:
        data = movimiento_schema.load(payload, partial=True)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    data.pop("id_movimiento", None)
    movimiento = service.update(movimiento_id, data)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return movimiento_schema.dump(movimiento)
