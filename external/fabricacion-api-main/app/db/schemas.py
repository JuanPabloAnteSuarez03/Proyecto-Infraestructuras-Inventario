# app/db/schemas.py
from pydantic import BaseModel
from typing import Optional

# --------- PIEZAS ---------
class PiezaBase(BaseModel):
    nombre: str
    codigo: str
    material: str

class PiezaCreate(PiezaBase):
    pass

class PiezaRead(PiezaBase):
    id: int

    class Config:
        orm_mode = True  


# --------- PLANOS ---------
class PlanoBase(BaseModel):
    nombre: str
    codigo: str

class PlanoCreate(PlanoBase):
    tiempo_fabricacion: Optional[int] = None  

class PlanoRead(PlanoBase):
    id: int
    tiempo_fabricacion: Optional[int]

    class Config:
        orm_mode = True

# --------- Solicitud para cálculo de piezas ---------
class SolicitudCalculoPiezas(BaseModel):
    """
    Entrada del endpoint /calculo_piezas

    - codigo: código del plano (Plano.codigo)
    - cantidad: unidades del producto a fabricar
    """
    codigo: str      # código del plano
    cantidad: int    # unidades del producto a fabricar


# --------- Detalle de pieza en el cálculo ---------
class PiezaCalculada(BaseModel):
    """
    Información de cada pieza requerida para el plano.
    """
    codigo_pieza: str   # código de la pieza (Pieza.codigo)
    unidad: int         # piezas por cada unidad del producto
    total_piezas: int   # piezas totales para la cantidad solicitada


# --------- Respuesta del cálculo de piezas ---------
class CalculoPiezasResponse(BaseModel):
    """
    Respuesta del endpoint /calculo_piezas
    """
    codigo: str                 # código del plano
    cantidad_solicitada: int    # cantidad de unidades del producto
    tiempo_fabricacion: int
    piezas: list[PiezaCalculada]

# --------- Relación Plano - Pieza ---------
class RelacionPiezaPlanoRequest(BaseModel):
    codigo_plano: str     # código del plano (ej. "PL-001")
    codigo_pieza: str     # código de la pieza (ej. "TOR-001")
    cantidad: int         # cuántas piezas lleva UNA unidad del producto


class RelacionPiezaPlanoRead(BaseModel):
    codigo_plano: str
    codigo_pieza: str
    cantidad: int
