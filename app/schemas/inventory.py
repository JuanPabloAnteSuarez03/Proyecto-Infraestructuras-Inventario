from marshmallow import fields, validate
from ..extensions import ma
from ..models import InventarioProducto, InventarioPieza, Proveedor, Movimiento
from ..domain import PRODUCT_CODES, PRODUCT_STATES


class InventarioProductoSchema(ma.SQLAlchemyAutoSchema):
    id_producto = ma.auto_field(required=True, validate=validate.OneOf(PRODUCT_CODES))
    estado = ma.auto_field(required=True, validate=validate.OneOf(PRODUCT_STATES))
    cantidad = ma.auto_field(required=True)

    class Meta:
        model = InventarioProducto
        include_fk = True
        load_instance = False


class InventarioPiezaSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = InventarioPieza
        include_fk = True
        load_instance = False


class ProveedorSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Proveedor
        include_fk = True
        load_instance = False

    piezas = ma.Nested("InventarioPiezaSchema", many=True)


class MovimientoSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Movimiento
        include_fk = True
        load_instance = False


class TransferenciaInventarioSchema(ma.Schema):
    id_producto = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_CODES)
    )
    estado_origen = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_STATES)
    )
    estado_destino = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_STATES)
    )
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))


class SolicitudReservaSchema(ma.Schema):
    id_producto = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_CODES)
    )
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))


class SolicitudDespachoSchema(ma.Schema):
    id_producto = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_CODES)
    )
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))


class IngresoInventarioSchema(ma.Schema):
    id_producto = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_CODES)
    )
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))
    estado = fields.String(
        load_default="Disponible", validate=validate.OneOf(PRODUCT_STATES)
    )


class SolicitudFabricacionSchema(ma.Schema):
    id_producto = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_CODES)
    )
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))


class SolicitudPiezasSchema(ma.Schema):
    id_pieza = fields.String(required=True)
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))


class SolicitudCalculoPiezasSchema(ma.Schema):
    codigo = fields.String(required=True, validate=validate.OneOf(PRODUCT_CODES))
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))
