from marshmallow import Schema, fields, validate, pre_load
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field
from ..models import InventarioProducto, InventarioPieza, Proveedor, Movimiento
from ..domain import PRODUCT_CODES, PRODUCT_STATES


class InventarioProductoSchema(SQLAlchemyAutoSchema):
    id_producto = auto_field(required=True, validate=validate.OneOf(PRODUCT_CODES))
    estado = auto_field(required=True, validate=validate.OneOf(PRODUCT_STATES))
    cantidad = auto_field(required=True)

    class Meta:
        model = InventarioProducto
        include_fk = True
        load_instance = False


class InventarioPiezaSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = InventarioPieza
        include_fk = True
        load_instance = False


class ProveedorSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Proveedor
        include_fk = True
        load_instance = False

    piezas = fields.Nested("InventarioPiezaSchema", many=True)


class MovimientoSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Movimiento
        include_fk = True
        load_instance = False


class TransferenciaInventarioSchema(Schema):
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


class SolicitudReservaSchema(Schema):
    id_producto = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_CODES)
    )
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))


class SolicitudDespachoSchema(Schema):
    id_producto = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_CODES)
    )
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))


class IngresoInventarioSchema(Schema):
    id_producto = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_CODES)
    )
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))
    estado = fields.String(
        load_default="Disponible", validate=validate.OneOf(PRODUCT_STATES)
    )

    @pre_load
    def normalize_producto_field(self, data, **kwargs):
        """Acepta 'codigo' como alias de 'id_producto' para compatibilidad con fábrica externa"""
        if "codigo" in data and "id_producto" not in data:
            data["id_producto"] = data.pop("codigo")
        return data


class SolicitudFabricacionSchema(Schema):
    id_producto = fields.String(
        required=True, validate=validate.OneOf(PRODUCT_CODES)
    )
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))


class SolicitudPiezasSchema(Schema):
    id_pieza = fields.String(required=True)
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))


class SolicitudCalculoPiezasSchema(Schema):
    codigo = fields.String(required=True, validate=validate.OneOf(PRODUCT_CODES))
    cantidad = fields.Integer(required=True, validate=validate.Range(min=1))
