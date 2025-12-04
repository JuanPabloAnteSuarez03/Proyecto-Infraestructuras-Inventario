from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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
from ..database import get_db
from ..services.inventario_productos_service import InventarioProductosService

router = APIRouter(prefix="/api/productos", tags=["productos"])
producto_schema = InventarioProductoSchema()
productos_schema = InventarioProductoSchema(many=True)
transfer_schema = TransferenciaInventarioSchema()
reserva_schema = SolicitudReservaSchema()
despacho_schema = SolicitudDespachoSchema()
ingreso_schema = IngresoInventarioSchema()


@router.get("")
def listar_productos(db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    productos = service.list()
    return productos_schema.dump(productos)


@router.get("/{producto_id}")
def listar_estados_producto(producto_id: str, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    registros = service.list_by_producto(producto_id)
    if not registros:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return productos_schema.dump(registros)


@router.get("/{producto_id}/{estado}")
def obtener_producto(producto_id: str, estado: str, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    producto = service.retrieve(producto_id, estado)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto_schema.dump(producto)


@router.post("", status_code=201)
def crear_producto(body: ProductoCreate, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    payload = body.model_dump()
    try:
        data = producto_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    producto = service.create(data)
    return producto_schema.dump(producto)


@router.delete("/{producto_id}/{estado}")
def eliminar_producto(producto_id: str, estado: str, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
    eliminado = service.delete(producto_id, estado)
    if not eliminado:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {"message": "Producto eliminado"}


@router.put("/{producto_id}/{estado}")
def actualizar_producto(
    producto_id: str, estado: str, body: ProductoUpdate, db: Session = Depends(get_db)
):
    service = InventarioProductosService(db)
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
def incrementar_producto(body: IngresoProducto, db: Session = Depends(get_db)):
    from app.services import OrdenesFabricacionService

    service = InventarioProductosService(db)
    payload = body.model_dump()
    try:
        data = ingreso_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)

    codigo = data["id_producto"]
    cantidad = data["cantidad"]
    estado = data.get("estado", "Disponible")

    try:
        producto = service.incrementar(
            producto_id=codigo,
            estado=estado,
            cantidad=cantidad,
        )

        # Cerrar órdenes esperando fabricación para este producto
        from app.models.entities import OrdenFabricacion

        # Buscar órdenes y completar la más pequeña primero (para progreso visible)
        # Ordenar por: 1) cantidad pendiente más pequeña, 2) ID más antiguo (FIFO)
        orden = (
            db.query(OrdenFabricacion)
            .filter(
                OrdenFabricacion.id_producto == codigo.upper(),
                OrdenFabricacion.estado == "esperando_fabricacion"
            )
            .order_by(
                OrdenFabricacion.cantidad.asc(),  # Completar órdenes pequeñas primero
                OrdenFabricacion.id.asc()  # FIFO como desempate
            )
            .with_for_update()  # Bloquea la fila - otras transacciones ESPERAN
            .first()
        )

        if orden:
            # Obtener entregas parciales acumuladas (optimizado)
            detalle = orden.detalle if isinstance(orden.detalle, dict) else {}
            entrega_acumulada = detalle.get("entrega_acumulada", 0) + cantidad

            # Actualizar detalle con nuevo acumulado (forzar detección de cambio)
            orden.detalle = {**detalle, "entrega_acumulada": entrega_acumulada}

            # Actualizar estado si se completó la orden
            completada = entrega_acumulada >= orden.cantidad
            if completada:
                orden.estado = "completada"

            # Commit ÚNICO (más rápido)
            db.commit()

            # Logging fuera de la transacción (no bloquea)
            if completada:
                print(
                    f"[INGRESO] ✓ Orden #{orden.id} completada. "
                    f"Pedido: {orden.cantidad}, recibido total: {entrega_acumulada} "
                    f"(última entrega: {cantidad})"
                )
            else:
                print(
                    f"[INGRESO] ⚠️ Entrega parcial para orden #{orden.id}: "
                    f"recibido {cantidad}, acumulado {entrega_acumulada} de {orden.cantidad}"
                )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return producto_schema.dump(producto)


@router.post("/transferencias")
def transferir_producto(body: Transferencia, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
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
def reservar_producto(body: Reserva, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
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
def despachar_producto(body: Despacho, db: Session = Depends(get_db)):
    service = InventarioProductosService(db)
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
