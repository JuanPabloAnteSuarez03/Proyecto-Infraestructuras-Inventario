from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class Pieza(Base):
    __tablename__ = "piezas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    # código como texto
    codigo = Column(String, nullable=False, unique=True, index=True)
    material = Column(String, nullable=False)

    # Relación con PiezaPlano (una pieza puede estar en muchos planos)
    planos = relationship("PiezaPlano", back_populates="pieza")


class Plano(Base):
    __tablename__ = "planos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    # código como texto
    codigo = Column(String, nullable=False, unique=True, index=True)

    # horas de fabricación por unidad (int), opcional
    tiempo_fabricacion = Column(Integer, nullable=True)

    # Relación con PiezaPlano (un plano usa muchas piezas)
    piezas = relationship("PiezaPlano", back_populates="plano")


class PiezaPlano(Base):
    __tablename__ = "pieza_plano"

    pieza_id = Column(Integer, ForeignKey("piezas.id"), primary_key=True)
    plano_id = Column(Integer, ForeignKey("planos.id"), primary_key=True)
    cantidad = Column(Integer, nullable=False)

    pieza = relationship("Pieza", back_populates="planos")
    plano = relationship("Plano", back_populates="piezas")
