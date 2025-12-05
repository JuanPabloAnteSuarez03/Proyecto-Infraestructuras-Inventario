# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import DATABASE_URL

# Crea el engine a partir de la URL de BD
engine = create_engine(DATABASE_URL)

# Creador de sesiones (cada request usará una)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base a partir de la cual declaramos nuestros modelos
Base = declarative_base()


# Dependencia para FastAPI:
# cuando un endpoint necesita acceso a BD, recibe un `db: Session = Depends(get_db)`
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
