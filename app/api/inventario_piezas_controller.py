from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..schemas.api_models import PiezaCreate, PiezaUpdate
from ..database import get_db
from ..services import InventarioPiezasService

router = APIRouter(prefix="/api/piezas", tags=["piezas"])


def serialize_pieza(pieza):
    return {
        "id_pieza": pieza.id_pieza,
        "cantidad": pieza.cantidad,
        "id_proveedor": pieza.id_proveedor,
    }


@router.get("")
def listar_piezas(db: Session = Depends(get_db)):
    service = InventarioPiezasService(db)
    piezas = service.list()
    return [serialize_pieza(p) for p in piezas]


@router.get("/{pieza_id}")
def obtener_pieza(pieza_id: str, db: Session = Depends(get_db)):
    service = InventarioPiezasService(db)
    pieza = service.retrieve(pieza_id)
    if not pieza:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    return serialize_pieza(pieza)


@router.post("", status_code=201)
def crear_pieza(body: PiezaCreate, db: Session = Depends(get_db)):
    service = InventarioPiezasService(db)
    payload = body.model_dump()
    pieza = service.create(payload)
    return serialize_pieza(pieza)


@router.delete("/{pieza_id}")
def eliminar_pieza(pieza_id: str, db: Session = Depends(get_db)):
    service = InventarioPiezasService(db)
    eliminado = service.delete(pieza_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    return {"message": "Pieza eliminada"}


@router.post("/reset")
def resetear_piezas(db: Session = Depends(get_db)):
    service = InventarioPiezasService(db)
    total = service.reset_all()
    return {"message": "Inventario de piezas reseteado", "registros": total}


@router.put("/{pieza_id}")
def actualizar_pieza(pieza_id: str, body: PiezaUpdate, db: Session = Depends(get_db)):
    service = InventarioPiezasService(db)
    payload = body.model_dump(exclude_unset=True)
    payload.pop("id_pieza", None)
    pieza = service.update(pieza_id, payload)
    if not pieza:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    return serialize_pieza(pieza)
