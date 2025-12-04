from fastapi import APIRouter, Depends, HTTPException, Request
from marshmallow import ValidationError
import httpx
import os
from sqlalchemy.orm import Session
from ..services import (
    FabricacionService,
    InventarioProductosService,
    OrdenesFabricacionService,
    ProveedoresService,
)
from ..repositories import InventarioPiezasRepository
from ..schemas.inventory import SolicitudFabricacionSchema, SolicitudCalculoPiezasSchema
from ..schemas.api_models import SolicitudFabricacion, CalculoPiezas, OrdenFabricacionAsync
from ..tasks import queue, procesar_orden_fabricacion
from ..database import get_db

router = APIRouter(prefix="/api/fabricacion", tags=["fabricacion"])
solicitud_schema = SolicitudFabricacionSchema()
calculo_schema = SolicitudCalculoPiezasSchema()
fabricacion_service = FabricacionService()


@router.get("/plan/{codigo}")
def obtener_plan(
    codigo: str, cantidad: int = 1, session: Session = Depends(get_db)
):
    piezas_repository = InventarioPiezasRepository(session)
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
def producir_lote(body: SolicitudFabricacion, session: Session = Depends(get_db)):
    payload = body.model_dump()
    try:
        data = solicitud_schema.load(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.messages)
    try:
        productos_service = InventarioProductosService(session)
        resultado = productos_service.fabricar_productos(
            producto_id=data["id_producto"], cantidad=data["cantidad"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return resultado


@router.post("/ordenes", status_code=202)
def crear_orden_fabricacion(
    body: OrdenFabricacionAsync, session: Session = Depends(get_db)
):
    """
    Crea orden de fabricación con confirmación sincrónica a fábrica externa.

    Flujo:
    1. Calcular piezas necesarias
    2. Verificar disponibilidad en inventario
    3. Solicitar piezas faltantes a proveedores si necesario
    4. Confirmar fabricación con fábrica externa
    5. Encolar worker para consumir piezas y esperar webhook
    """
    payload = body.model_dump()
    codigo = payload["id_producto"].upper()
    cantidad = payload["cantidad"]

    ordenes_service = OrdenesFabricacionService(session)
    piezas_repo = InventarioPiezasRepository(session)
    proveedores_service = ProveedoresService(session, piezas_repository=piezas_repo)

    orden = ordenes_service.create(
        {"id_producto": codigo, "cantidad": cantidad, "estado": "calculando"}
    )

    detalle: dict[str, list | dict | str] = {"pasos": []}

    try:
        detalle["pasos"].append("Calculando piezas necesarias...")
        plan = fabricacion_service.solicitar_plan(codigo, cantidad)
        detalle["plan"] = {
            "materiales": plan.materiales,
            "tiempo_produccion": plan.tiempo_produccion,
        }
        detalle["pasos"].append(f"Se necesitan {len(plan.materiales)} tipos de piezas")

        detalle["pasos"].append("Verificando inventario de piezas...")
        tiempo_reabastecimiento = 0

        for material in plan.materiales:
            pieza = piezas_repo.get_by_id(material["id_pieza"])
            disponible = pieza.cantidad if pieza else 0
            necesario = material["cantidad"]

            if disponible < necesario:
                faltante = necesario - disponible
                detalle["pasos"].append(
                    f"Pieza {material['id_pieza']}: faltan {faltante} unidades"
                )

                resultado_proveedor = proveedores_service.solicitar_piezas(
                    material["id_pieza"], faltante
                )
                tiempo_reabastecimiento = max(
                    tiempo_reabastecimiento, resultado_proveedor["tiempo_entrega"]
                )
                detalle["pasos"].append(
                    f"Solicitado a proveedor: {faltante} x {material['id_pieza']}"
                )

        session.commit()

        detalle["pasos"].append("Enviando confirmación a fábrica externa...")
        orden.estado = "confirmando"
        session.commit()

        confirmacion = fabricacion_service.confirmar_fabricacion_externa(
            codigo, cantidad
        )

        if confirmacion and confirmacion.get("status") == "ok":
            orden.estado = "confirmado"
            detalle["pasos"].append("✓ Fábrica externa confirmó la orden")
            detalle["confirmacion_fabrica"] = confirmacion
            detalle["fabricacion_externa"] = True

            queue.enqueue(procesar_orden_fabricacion, orden.id)
            detalle["pasos"].append(
                "Worker encolado para consumir piezas y esperar productos"
            )
        else:
            orden.estado = "confirmacion_fallida"
            detalle["pasos"].append("✗ Fábrica externa no disponible")
            detalle["pasos"].append(
                "No se permite fabricación local - orden marcada como fallida"
            )
            detalle["fabricacion_externa"] = False
            queue.enqueue(procesar_orden_fabricacion, orden.id)

        orden.tiempo_estimado = tiempo_reabastecimiento + plan.tiempo_produccion
        orden.detalle = detalle
        session.commit()

        return {
            "id": orden.id,
            "estado": orden.estado,
            "tiempo_estimado": orden.tiempo_estimado,
            "detalle": detalle,
        }

    except Exception as exc:  # pylint: disable=broad-except
        orden.estado = "fallida"
        orden.detalle = {"error": str(exc), "pasos": detalle.get("pasos", [])}
        session.commit()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/ordenes/{orden_id}")
def obtener_orden_fabricacion(orden_id: int, session: Session = Depends(get_db)):
    ordenes_service = OrdenesFabricacionService(session)
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
def listar_ordenes_fabricacion(session: Session = Depends(get_db)):
    ordenes_service = OrdenesFabricacionService(session)
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


@router.get("/external/status")
def verificar_servicio_externo():
    """Proxy endpoint para verificar el estado del servicio externo de fabricación"""
    base_url = os.getenv("FABRICA_BASE_URL", "").rstrip("/")
    if not base_url:
        return {"conectado": False, "planos": {}}

    planos = {}
    for plano_id, codigo in [(1, "S1"), (2, "S2")]:
        try:
            resp = httpx.get(f"{base_url}/fabricacion/planos/{plano_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                planos[codigo] = {
                    "disponible": True,
                    "tiempo_fabricacion": data.get("tiempo_fabricacion"),
                    "nombre": data.get("nombre"),
                }
            else:
                planos[codigo] = {"disponible": False}
        except Exception:
            planos[codigo] = {"disponible": False}

    return {
        "conectado": any(p.get("disponible") for p in planos.values()),
        "base_url": base_url,
        "planos": planos,
    }


@router.get("/external/planos/{plano_id}")
def obtener_plano_externo(plano_id: int):
    """Proxy endpoint para obtener información de un plano del servicio externo"""
    base_url = os.getenv("FABRICA_BASE_URL", "").rstrip("/")
    if not base_url:
        raise HTTPException(status_code=503, detail="Servicio externo no configurado")

    try:
        resp = httpx.get(f"{base_url}/fabricacion/planos/{plano_id}", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail="Plano no encontrado en servicio externo"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Servicio externo no disponible: {str(exc)}"
        )


@router.post("/webhook/productos_terminados")
async def recibir_productos_fabricados(
    request: Request, session: Session = Depends(get_db)
):
    """
    Webhook para que la fábrica externa notifique productos terminados.

    Expected body:
    {
        "codigo": "S1",
        "cantidad": 1500,
        "estado": "Disponible"  # opcional, default: "Disponible"
    }
    """
    try:
        body = await request.json()
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[WEBHOOK] Error parseando JSON: {exc}")
        raise HTTPException(status_code=400, detail=f"JSON inválido: {str(exc)}")

    print(f"[WEBHOOK] Recibido: {body}")

    codigo = body.get("codigo")
    cantidad = body.get("cantidad")
    estado = body.get("estado", "Disponible")

    if not codigo or not cantidad:
        raise HTTPException(
            status_code=400, detail="Se requieren 'codigo' y 'cantidad'"
        )

    try:
        productos_service = InventarioProductosService(session)
        ordenes_service = OrdenesFabricacionService(session)

        producto = productos_service.incrementar(
            producto_id=codigo, cantidad=cantidad, estado=estado
        )

        # Cerrar órdenes esperando fabricación para este producto.
        ordenes_pendientes = ordenes_service.list()
        for orden in ordenes_pendientes:
            if (
                orden.id_producto == codigo.upper()
                and orden.estado == "esperando_fabricacion"
            ):
                # Si la fábrica envía más de lo pedido, también se completa.
                if cantidad >= orden.cantidad:
                    orden.estado = "completada"
                    session.commit()
                    print(
                        f"[WEBHOOK] ✓ Orden #{orden.id} completada. "
                        f"Pedido: {orden.cantidad}, recibido: {cantidad}"
                    )
                    break
                else:
                    # Entrega parcial: marcar detalle y esperar siguiente webhook
                    if isinstance(orden.detalle, dict):
                        orden.detalle["entrega_parcial"] = cantidad
                    else:
                        orden.detalle = {"entrega_parcial": cantidad}
                    session.commit()
                    print(
                        f"[WEBHOOK] ⚠️ Entrega parcial para orden #{orden.id}: "
                        f"recibido {cantidad} de {orden.cantidad}"
                    )
                    break

        return {
            "status": "ok",
            "mensaje": f"Recibidos {cantidad} productos {codigo}",
            "inventario_actual": producto.cantidad,
        }
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(
            status_code=500, detail=f"Error procesando productos: {str(exc)}"
        )
