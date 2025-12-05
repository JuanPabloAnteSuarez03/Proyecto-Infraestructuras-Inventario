import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..schemas.api_models import (
    ProductoCreate,
    ProductoUpdate,
    IngresoProducto,
    Transferencia,
    Reserva,
    Despacho,
)
from ..database import get_db
from ..services import (
    InventarioProductosService,
    EntregasFabricacionService,
)

router = APIRouter(prefix="/api/productos", tags=["productos"])
logger = logging.getLogger(__name__)


def serialize_producto(prod):
    return {
        "id_producto": prod.id_producto,
        "estado": prod.estado,
        "cantidad": prod.cantidad,
    }


@router.get("")
def listar_productos(db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    productos = service.list()
    return [serialize_producto(p) for p in productos]


@router.get("/{producto_id}")
def listar_estados_producto(producto_id: str, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    registros = service.list_by_producto(producto_id)
    if not registros:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return [serialize_producto(p) for p in registros]


@router.get("/{producto_id}/{estado}")
def obtener_producto(producto_id: str, estado: str, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    producto = service.retrieve(producto_id, estado)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return serialize_producto(producto)


@router.post("", status_code=201)
def crear_producto(body: ProductoCreate, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    payload = body.model_dump()
    producto = service.create(payload)
    return serialize_producto(producto)


@router.delete("/{producto_id}/{estado}")
def eliminar_producto(producto_id: str, estado: str, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    eliminado = service.delete(producto_id, estado)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"message": "Producto eliminado"}


@router.post("/reset")
def resetear_productos(db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    total = service.reset_all()
    return {"message": "Inventario de productos reseteado", "registros": total}


@router.put("/{producto_id}/{estado}")
def actualizar_producto(
    producto_id: str, estado: str, body: ProductoUpdate, db: Session = Depends(get_db)
):
    service = InventarioProductosService(db)
    payload = body.model_dump()
    producto = service.update(producto_id, estado, {"cantidad": payload["cantidad"]})
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return serialize_producto(producto)


@router.post("/ingresos")
def incrementar_producto(body: IngresoProducto, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    payload = body.model_dump()
    logger.info("[INGRESO DEBUG] Payload recibido: %s", payload)
    codigo = payload.get("id_producto")
    cantidad = payload.get("cantidad")
    estado = payload.get("estado") or "Disponible"

    try:
        producto = service.incrementar(
            producto_id=codigo,
            estado=estado,
            cantidad=cantidad,
        )

        estados_objetivo = ("esperando_fabricacion", "consumiendo_piezas", "confirmado")
        entregas_service = EntregasFabricacionService(db)
        entregas_service.registrar_entrega(
            codigo=codigo,
            cantidad=cantidad,
            estados_objetivo=estados_objetivo,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return serialize_producto(producto)


@router.post("/transferencias")
def transferir_producto(body: Transferencia, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    payload = body.model_dump()
    try:
        registros = service.transferir(
            producto_id=payload["id_producto"],
            estado_origen=payload["estado_origen"],
            estado_destino=payload["estado_destino"],
            cantidad=payload["cantidad"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [serialize_producto(p) for p in registros]


@router.post("/reservas")
def reservar_producto(body: Reserva, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    payload = body.model_dump()
    try:
        resultado = service.reservar_para_venta(
            producto_id=payload["id_producto"], cantidad=payload["cantidad"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return resultado


@router.post("/despachos")
def despachar_producto(body: Despacho, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    payload = body.model_dump()
    try:
        resultado = service.despachar_para_venta(
            producto_id=payload["id_producto"], cantidad=payload["cantidad"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return resultado
