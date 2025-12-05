# app/core/config.py
import os
from dotenv import load_dotenv
load_dotenv()
# Configuración de la base de datos
DB_USER = os.getenv("DB_USER", "fabricacion_user")
DB_PASS = os.getenv("DB_PASS", "fabricacion_pass")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fabricacion_db")

#Rutas de inventario
API_PATH_INVENTARIO = os.getenv("API_PATH_INVENTARIO", "localhost")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 6))

# Para Postgres:
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


