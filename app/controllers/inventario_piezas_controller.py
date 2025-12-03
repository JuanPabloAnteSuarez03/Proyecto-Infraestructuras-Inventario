from fastapi import APIRouter, HTTPException
from marshmallow import ValidationError
from ..schemas.inventory import InventarioPiezaSchema
from ..schemas.api_models import PiezaCreate, PiezaUpdate
from ..services.inventario_piezas_service import InventarioPiezasService

router = APIRouter(prefix="/api/piezas", tags=["piezas"])
service = InventarioPiezasService()
pieza_schema = InventarioPiezaSchema()
piezas_schema = InventarioPiezaSchema(many=True)


@router.get("")
def listar_piezas():
    piezas = service.list()
    return piezas_schema.dump(piezas)


@router.get("/{pieza_id}")
def obtener_pieza(pieza_id: str):
    pieza = service.retrieve(pieza_id)
    if not pieza:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    return pieza_schema.dump(pieza)


@router.post("", status_code=201)
def crear_pieza(body: PiezaCreate):
    payload = body.model_dump()
    try:
        data = pieza_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    pieza = service.create(data)
    return pieza_schema.dump(pieza)


@router.delete("/{pieza_id}")
def eliminar_pieza(pieza_id: str):
    eliminado = service.delete(pieza_id)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    return {"message": "Pieza eliminada"}


@router.put("/{pieza_id}")
def actualizar_pieza(pieza_id: str, body: PiezaUpdate):
    payload = body.model_dump(exclude_unset=True)
    try:
        data = pieza_schema.load(payload, partial=True)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    data.pop("id_pieza", None)
    pieza = service.update(pieza_id, data)
    if not pieza:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    return pieza_schema.dump(pieza)
