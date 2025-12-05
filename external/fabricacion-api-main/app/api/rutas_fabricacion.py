# app/api/rutas_fabricacion.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db, Base, engine
from app.db import models, schemas
from pydantic import BaseModel
from app.utils.fabricacion_utils import verificar_solicitud
from app.utils.fabricacion_workers import ejecutar_fabricacion

from app.core.queue_fabricacion import fabricacion_queue

Base.metadata.create_all(bind=engine)

router = APIRouter(
    prefix="/fabricacion",
    tags=["fabricacion"],
)

#////////////////////////////////////////
#EndPonits de Piezas
#////////////////////////////////////////
@router.get("/piezas", response_model=list[schemas.PiezaRead])
def listar_piezas(db: Session = Depends(get_db)):
    """
    Devuelve todas las piezas registradas.
    """
    piezas = db.query(models.Pieza).all()
    return piezas


@router.get("/piezas/{pieza_id}", response_model=schemas.PiezaRead)
def obtener_pieza(pieza_id: int, db: Session = Depends(get_db)):
    """
    Devuelve una pieza específica por ID.
    """
    pieza = db.query(models.Pieza).filter(models.Pieza.id == pieza_id).first()
    if not pieza:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")
    return pieza

@router.post(
    "/piezas",
    response_model=schemas.PiezaRead,
    status_code=status.HTTP_201_CREATED,
)
def crear_pieza(pieza: schemas.PiezaCreate, db: Session = Depends(get_db)):
    """
    Crea una nueva pieza en el catálogo de fabricación.

    - nombre: texto (ej. "Cadena estándar")
    - codigo: int (ej. 1001) — debe ser único
    - material: texto (ej. "Acero")
    """
    # Validar que no exista otra pieza con el mismo código
    existente = (
        db.query(models.Pieza)
        .filter(models.Pieza.codigo == pieza.codigo)
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=400,
            detail="Ya existe una pieza con ese código",
        )

    nueva = models.Pieza(
        nombre=pieza.nombre,
        codigo=pieza.codigo,
        material=pieza.material,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


#////////////////////////////////////////
#EndPont de Planos
#////////////////////////////////////////
@router.get("/planos", response_model=list[schemas.PlanoRead])
def listar_planos(db: Session = Depends(get_db)):
    """
    Devuelve todos los planos registrados.
    """
    planos = db.query(models.Plano).all()
    return planos

@router.get("/planos/{plano_id}", response_model=schemas.PlanoRead)
def obtener_plano(plano_id: int, db: Session = Depends(get_db)):
    """
    Devuelve un plano específico por ID.
    """
    plano = db.query(models.Plano).filter(models.Plano.id == plano_id).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Plano no encontrado")
    return plano

@router.post(
    "/planos",
    response_model=schemas.PlanoRead,
    status_code=status.HTTP_201_CREATED,
)
def crear_plano(plano: schemas.PlanoCreate, db: Session = Depends(get_db)):
    """
    Crea un nuevo plano de producto.

    - nombre: texto (ej. "Motosierra básica")
    - codigo: int (ej. 2001) — debe ser único
    - tiempo_fabricacion: horas estimadas por unidad (int), opcional
    """
    existente = (
        db.query(models.Plano)
        .filter(models.Plano.codigo == plano.codigo)
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=400,
            detail="Ya existe un plano con ese código",
        )

    nuevo = models.Plano(
        nombre=plano.nombre,
        codigo=plano.codigo,
        tiempo_fabricacion=plano.tiempo_fabricacion,  # horas (puede ser None)
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

#////////////////////////////////////////
# Cálculo de piezas necesarias
#////////////////////////////////////////
@router.post(
    "/calculo_piezas",
    response_model=schemas.CalculoPiezasResponse,
)
def calculo_piezas(
    solicitud: schemas.SolicitudCalculoPiezas,
    db: Session = Depends(get_db),
):
    """
    Dado el código de un plano y una cantidad de unidades,
    calcula cuántas piezas se necesitan en total.

    Entrada:
    - codigo: código del plano (Plano.codigo)
    - cantidad: número de unidades a fabricar

    Salida:
    - codigo: código del plano
    - cantidad_solicitada
    - piezas: lista con código_pieza, unidad, total_piezas
    """

    # 1. Verificar que el plano exista (por código, NO por id)
    plano = (
        db.query(models.Plano)
        .filter(models.Plano.codigo == solicitud.codigo)
        .first()
    )
    if not plano:
        raise HTTPException(status_code=404, detail="Plano no encontrado")

    if solicitud.cantidad <= 0:
        raise HTTPException(
            status_code=400,
            detail="La cantidad debe ser mayor que cero",
        )
    # 2. Buscar las piezas asociadas al plano en la tabla intermedia
    #    PiezaPlano(plano_id, pieza_id, cantidad)
    detalles = (
        db.query(models.PiezaPlano, models.Pieza)
        .join(models.Pieza, models.PiezaPlano.pieza_id == models.Pieza.id)
        .filter(models.PiezaPlano.plano_id == plano.id)
        .all()
    )

    if not detalles:
        raise HTTPException(
            status_code=400,
            detail="El plano no tiene piezas asociadas en la tabla pieza_plano",
        )

    piezas_resultado: list[schemas.PiezaCalculada] = []

    for detalle, pieza in detalles:
        # cantidad por unidad de producto (ej: 2 tornillos por motosierra)
        cantidad_por_unidad = detalle.cantidad

        # cantidad total = cantidad_por_unidad * unidades solicitadas
        cantidad_total = cantidad_por_unidad * solicitud.cantidad

        piezas_resultado.append(
            schemas.PiezaCalculada(
                codigo_pieza=str(pieza.codigo),
                unidad=cantidad_por_unidad,
                total_piezas=cantidad_total,
            )
        )

    #tiempo total en horas
    temp = solicitud.cantidad*plano.tiempo_fabricacion
    # 3. Armar la respuesta
    return schemas.CalculoPiezasResponse(
        codigo=str(plano.codigo),
        cantidad_solicitada=solicitud.cantidad,
        tiempo_fabricacion = temp,
        piezas=piezas_resultado,
    )


#///////////////////////////////////////////////
#Confirmacion de fabricacion
#///////////////////////////////////////////////
@router.post("/confirmar_fabricacion")
async def start_fabricacion(solicitud: schemas.SolicitudCalculoPiezas, db: Session = Depends(get_db)):

    await verificar_solicitud(solicitud, db)

    await fabricacion_queue.add_job({
        "codigo": solicitud.codigo,
        "cantidad": solicitud.cantidad
    })


    return {
        "status": "ok",
        "mensaje": f"Fabricación iniciada para {solicitud.cantidad} unidades del código {solicitud.codigo}"
    }


class TestEnt(BaseModel):
    codigo: str
    cantidad: int

@router.post("/test")
async def test_fabricacion(data: TestEnt, db: Session= Depends(get_db)):
    await verificar_solicitud(data,db)
    return status.HTTP_200_OK


@router.post(
    "/relacionar_pieza",
    response_model=schemas.RelacionPiezaPlanoRead,
    status_code=status.HTTP_201_CREATED,
)
def relacionar_pieza_con_plano(
    relacion: schemas.RelacionPiezaPlanoRequest,
    db: Session = Depends(get_db),
):
    # 1. Buscar plano por código
    plano = (
        db.query(models.Plano)
        .filter(models.Plano.codigo == relacion.codigo_plano)
        .first()
    )
    if not plano:
        raise HTTPException(status_code=404, detail="Plano no encontrado")

    # 2. Buscar pieza por código
    pieza = (
        db.query(models.Pieza)
        .filter(models.Pieza.codigo == relacion.codigo_pieza)
        .first()
    )
    if not pieza:
        raise HTTPException(status_code=404, detail="Pieza no encontrada")

    if relacion.cantidad <= 0:
        raise HTTPException(
            status_code=400,
            detail="La cantidad debe ser mayor que cero",
        )

    # 3. Ver si ya existe la relación pieza-plano
    enlace = (
        db.query(models.PiezaPlano)
        .filter(
            models.PiezaPlano.plano_id == plano.id,
            models.PiezaPlano.pieza_id == pieza.id,
        )
        .first()
    )

    if enlace:
        # Actualizamos la cantidad usando UPDATE (sin tocar el atributo Column)
        (
            db.query(models.PiezaPlano)
            .filter(
                models.PiezaPlano.plano_id == plano.id,
                models.PiezaPlano.pieza_id == pieza.id,
            )
            .update({"cantidad": relacion.cantidad})
        )
    else:
        # Creamos la relación
        enlace = models.PiezaPlano(
            plano_id=plano.id,
            pieza_id=pieza.id,
            cantidad=relacion.cantidad,
        )
        db.add(enlace)

    db.commit()

    # 4. Respuesta (conversión explícita a str/int para contentar al type checker)
    return schemas.RelacionPiezaPlanoRead(
        codigo_plano=str(plano.codigo),
        codigo_pieza=str(pieza.codigo),
        cantidad=int(relacion.cantidad),
    )

