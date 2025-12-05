from app.db import models, schemas
from fastapi import HTTPException



async def verificar_solicitud(solicitud, db):
    
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