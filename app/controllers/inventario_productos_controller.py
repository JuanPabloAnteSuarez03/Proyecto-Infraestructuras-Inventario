from fastapi import APIRouter, HTTPException
from marshmallow import ValidationError
from ..schemas.inventory import (
    InventarioProductoSchema,
    TransferenciaInventarioSchema,
    SolicitudReservaSchema,
    SolicitudDespachoSchema,
    IngresoInventarioSchema,
)
from ..schemas.api_models import (
    ProductoCreate,
    ProductoUpdate,
    IngresoProducto,
    Transferencia,
    Reserva,
    Despacho,
)
from ..services.inventario_productos_service import InventarioProductosService

router = APIRouter(prefix="/api/productos", tags=["productos"])
service = InventarioProductosService()
producto_schema = InventarioProductoSchema()
productos_schema = InventarioProductoSchema(many=True)
transfer_schema = TransferenciaInventarioSchema()
reserva_schema = SolicitudReservaSchema()
despacho_schema = SolicitudDespachoSchema()
ingreso_schema = IngresoInventarioSchema()


@router.get("")
def listar_productos():
    productos = service.list()
    return productos_schema.dump(productos)


@router.get("/{producto_id}")
def listar_estados_producto(producto_id: str):
    registros = service.list_by_producto(producto_id)
    if not registros:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return productos_schema.dump(registros)


@router.get("/{producto_id}/{estado}")
def obtener_producto(producto_id: str, estado: str):
    producto = service.retrieve(producto_id, estado)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto_schema.dump(producto)


@router.post("", status_code=201)
def crear_producto(body: ProductoCreate):
    payload = body.model_dump()
    try:
        data = producto_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    producto = service.create(data)
    return producto_schema.dump(producto)


@router.delete("/{producto_id}/{estado}")
def eliminar_producto(producto_id: str, estado: str):
    eliminado = service.delete(producto_id, estado)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"message": "Producto eliminado"}


@router.put("/{producto_id}/{estado}")
def actualizar_producto(producto_id: str, estado: str, body: ProductoUpdate):
    payload = body.model_dump()
    payload["id_producto"] = producto_id
    payload["estado"] = estado
    try:
        data = producto_schema.load(payload, partial=("cantidad",))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    if "cantidad" not in data:
        raise HTTPException(status_code=400, detail="Debe especificar la cantidad")
    producto = service.update(producto_id, estado, {"cantidad": data["cantidad"]})
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto_schema.dump(producto)


@router.post("/ingresos")
def incrementar_producto(body: IngresoProducto):
    payload = body.model_dump()
    try:
        data = ingreso_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    try:
        producto = service.incrementar(
            producto_id=data["id_producto"],
            estado=data.get("estado", "Disponible"),
            cantidad=data["cantidad"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return producto_schema.dump(producto)


@router.post("/transferencias")
def transferir_producto(body: Transferencia):
    payload = body.model_dump()
    try:
        data = transfer_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    try:
        registros = service.transferir(
            producto_id=data["id_producto"],
            estado_origen=data["estado_origen"],
            estado_destino=data["estado_destino"],
            cantidad=data["cantidad"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return productos_schema.dump(registros)


@router.post("/reservas")
def reservar_producto(body: Reserva):
    payload = body.model_dump()
    try:
        data = reserva_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    try:
        resultado = service.reservar_para_venta(
            producto_id=data["id_producto"], cantidad=data["cantidad"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return resultado


@router.post("/despachos")
def despachar_producto(body: Despacho):
    payload = body.model_dump()
    try:
        data = despacho_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    try:
        resultado = service.despachar_para_venta(
            producto_id=data["id_producto"], cantidad=data["cantidad"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return resultado
