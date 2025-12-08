"""
Sales Integration API (v1)
Compatible con la API de ventas para integración con el sistema de ventas externo.
"""
import logging
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from ..database import get_db
from ..services import InventarioProductosService

router = APIRouter(prefix="/api/v1", tags=["sales-integration"])
logger = logging.getLogger(__name__)

# Cargar catálogo de productos
CATALOG_PATH = Path(__file__).parent.parent / "data" / "seed" / "products_catalog.json"


def load_catalog():
    """Carga el catálogo de productos desde el archivo JSON."""
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando catálogo de productos: {e}")
        return []


def build_product_response(catalog_item: dict, inventory_data: dict) -> dict:
    """
    Construye la respuesta de producto combinando datos del catálogo con inventario real.

    Args:
        catalog_item: Item del catálogo con metadata (SKU, nombre, precio, etc.)
        inventory_data: Datos de inventario (cantidad disponible, estado)

    Returns:
        dict con el formato esperado por la API de ventas
    """
    # Determinar disponibilidad basada en el inventario real
    stock_quantity = inventory_data.get("cantidad", 0)

    # Si hay stock disponible, cambiar availabilityType a STOCK
    availability_type = catalog_item.get("availabilityType", "MANUFACTURING")
    estimated_days = catalog_item.get("estimatedDays")

    if stock_quantity > 0:
        availability_type = "STOCK"
        estimated_days = None

    return {
        "id": catalog_item["id"],
        "sku": catalog_item["sku"],
        "name": catalog_item["name"],
        "description": catalog_item.get("description", ""),
        "price": catalog_item["price"],
        "stockQuantity": stock_quantity,
        "availabilityType": availability_type,
        "estimatedDays": estimated_days,
        "active": catalog_item.get("active", True),
        "category": catalog_item.get("category", ""),
        "brand": catalog_item.get("brand", ""),
        "imageUrl": catalog_item.get("imageUrl", ""),
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
    }


@router.get("/products")
def list_products(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Lista todos los productos disponibles en el catálogo con información de inventario.

    Compatible con el formato esperado por la API de ventas.
    """
    catalog = load_catalog()
    service = InventarioProductosService(db)

    products = []
    for catalog_item in catalog:
        internal_id = catalog_item["internalId"]

        # Obtener inventario disponible para este producto
        try:
            inventory_records = service.list_by_producto(internal_id)
            # Sumar todas las cantidades disponibles (estado "Disponible")
            total_stock = sum(
                rec.cantidad for rec in inventory_records
                if rec.estado == "Disponible"
            )
            inventory_data = {"cantidad": total_stock}
        except Exception:
            inventory_data = {"cantidad": 0}

        product = build_product_response(catalog_item, inventory_data)
        products.append(product)

    # Aplicar paginación
    paginated_products = products[offset:offset + limit]

    return {
        "data": paginated_products,
        "total": len(products),
        "limit": limit,
        "offset": offset
    }


@router.get("/products/search")
def search_products(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Busca productos por nombre, descripción o SKU.

    Args:
        query: Término de búsqueda
        limit: Número máximo de resultados
        offset: Offset para paginación

    Returns:
        Lista de productos que coinciden con la búsqueda
    """
    catalog = load_catalog()
    service = InventarioProductosService(db)

    # Buscar en el catálogo
    query_lower = query.lower()
    matched_products = []

    for catalog_item in catalog:
        # Buscar en nombre, descripción, SKU, ID interno
        if (
            query_lower in catalog_item.get("name", "").lower() or
            query_lower in catalog_item.get("description", "").lower() or
            query_lower in catalog_item.get("sku", "").lower() or
            query_lower in catalog_item.get("internalId", "").lower()
        ):
            internal_id = catalog_item["internalId"]

            # Obtener inventario
            try:
                inventory_records = service.list_by_producto(internal_id)
                total_stock = sum(
                    rec.cantidad for rec in inventory_records
                    if rec.estado == "Disponible"
                )
                inventory_data = {"cantidad": total_stock}
            except Exception:
                inventory_data = {"cantidad": 0}

            product = build_product_response(catalog_item, inventory_data)
            matched_products.append(product)

    # Aplicar paginación
    paginated_products = matched_products[offset:offset + limit]

    return {
        "data": paginated_products,
        "total": len(matched_products),
        "limit": limit,
        "offset": offset
    }


@router.get("/products/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    """
    Obtiene un producto específico por su ID.

    Args:
        product_id: ID del producto (ej: "prod-s1")

    Returns:
        Detalles del producto
    """
    catalog = load_catalog()
    service = InventarioProductosService(db)

    # Buscar en el catálogo
    catalog_item = next((item for item in catalog if item["id"] == product_id), None)

    if not catalog_item:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    internal_id = catalog_item["internalId"]

    # Obtener inventario
    try:
        inventory_records = service.list_by_producto(internal_id)
        total_stock = sum(
            rec.cantidad for rec in inventory_records
            if rec.estado == "Disponible"
        )
        inventory_data = {"cantidad": total_stock}
    except Exception:
        inventory_data = {"cantidad": 0}

    return build_product_response(catalog_item, inventory_data)


@router.get("/products/{product_id}/availability")
def check_availability(product_id: str, quantity: int = Query(1, ge=1), db: Session = Depends(get_db)):
    """
    Verifica la disponibilidad de un producto para una cantidad específica.

    Args:
        product_id: ID del producto
        quantity: Cantidad solicitada

    Returns:
        Información de disponibilidad
    """
    catalog = load_catalog()
    service = InventarioProductosService(db)

    # Buscar en el catálogo
    catalog_item = next((item for item in catalog if item["id"] == product_id), None)

    if not catalog_item:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    internal_id = catalog_item["internalId"]

    # Obtener inventario
    try:
        inventory_records = service.list_by_producto(internal_id)
        total_stock = sum(
            rec.cantidad for rec in inventory_records
            if rec.estado == "Disponible"
        )
    except Exception:
        total_stock = 0

    available = total_stock >= quantity
    availability_type = catalog_item.get("availabilityType", "MANUFACTURING")
    estimated_days = catalog_item.get("estimatedDays")

    # Si hay stock, es disponible inmediatamente
    if total_stock >= quantity:
        availability_type = "STOCK"
        estimated_days = None

    return {
        "productId": product_id,
        "requestedQuantity": quantity,
        "available": available,
        "stockQuantity": total_stock,
        "availabilityType": availability_type,
        "estimatedDays": estimated_days,
        "canReserve": available  # Solo se puede reservar si hay stock disponible
    }


# Endpoints de reservaciones (simplificados para empezar)
@router.post("/reservations")
def create_reservation(body: dict, db: Session = Depends(get_db)):
    """
    Crea una reservación de producto.

    Por ahora es un stub - la lógica completa de reservaciones se implementará
    cuando se conecte con el sistema de órdenes de fabricación.
    """
    product_id = body.get("productId")
    quantity = body.get("quantity", 1)
    customer_id = body.get("customerId")

    if not product_id or not customer_id:
        raise HTTPException(
            status_code=400,
            detail="productId y customerId son requeridos"
        )

    # Verificar disponibilidad
    availability = check_availability(product_id, quantity, db)

    if not availability["canReserve"]:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficiente stock para reservar {quantity} unidades"
        )

    # TODO: Implementar lógica de reservación real
    # Por ahora retornamos una respuesta de éxito

    reservation_id = f"res-{product_id}-{datetime.now().timestamp()}"

    return {
        "reservationId": reservation_id,
        "productId": product_id,
        "quantity": quantity,
        "customerId": customer_id,
        "status": "PENDING",
        "createdAt": datetime.now().isoformat(),
        "expiresAt": None  # TODO: Calcular expiración
    }


@router.post("/reservations/{reservation_id}/confirm")
def confirm_reservation(reservation_id: str):
    """
    Confirma una reservación existente.

    Por ahora es un stub.
    """
    # TODO: Implementar lógica de confirmación
    return {
        "reservationId": reservation_id,
        "status": "CONFIRMED",
        "confirmedAt": datetime.now().isoformat()
    }


@router.delete("/reservations/{reservation_id}")
def release_reservation(reservation_id: str):
    """
    Libera/cancela una reservación.

    Por ahora es un stub.
    """
    # TODO: Implementar lógica de cancelación
    return {
        "reservationId": reservation_id,
        "status": "CANCELLED",
        "cancelledAt": datetime.now().isoformat()
    }
