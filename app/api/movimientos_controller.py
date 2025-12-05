from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..schemas.api_models import MovimientoCreate, MovimientoUpdate
from ..database import get_db
from ..services import MovimientosService

router = APIRouter(prefix="/api/movimientos", tags=["movimientos"])


def serialize_movimiento(m):
    return {
        "id_movimiento": m.id_movimiento,
        "id_objeto": m.id_objeto,
        "tipo_objeto": m.tipo_objeto,
        "cantidad": m.cantidad,
        "direccion": m.direccion,
    }


@router.get("")
def listar_movimientos(db: Session = Depends(get_db)):
    service = MovimientosService(db)
    movimientos = service.list()
    return [serialize_movimiento(m) for m in movimientos]


@router.get("/{movimiento_id}")
def obtener_movimiento(movimiento_id: int, db: Session = Depends(get_db)):
    service = MovimientosService(db)
    movimiento = service.retrieve(movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return serialize_movimiento(movimiento)


@router.post("", status_code=201)
def crear_movimiento(body: MovimientoCreate, db: Session = Depends(get_db)):
    service = MovimientosService(db)
    payload = body.model_dump()
    movimiento = service.create(payload)
    return serialize_movimiento(movimiento)


@router.delete("/{movimiento_id}")
def eliminar_movimiento(movimiento_id: int, db: Session = Depends(get_db)):
    service = MovimientosService(db)
    eliminado = service.delete(movimiento_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return {"message": "Movimiento eliminado"}


@router.put("/{movimiento_id}")
def actualizar_movimiento(
    movimiento_id: int, body: MovimientoUpdate, db: Session = Depends(get_db)
):
    service = MovimientosService(db)
    payload = body.model_dump(exclude_unset=True)
    payload.pop("id_movimiento", None)
    movimiento = service.update(movimiento_id, payload)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return serialize_movimiento(movimiento)
