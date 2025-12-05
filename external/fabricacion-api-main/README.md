# Servicio de Fabricación – Proyecto Final Infraestructuras Paralelas

Microservicio **Fabricación** de una empresa simulada (motosierras) para la materia de **Infraestructuras Paralelas y Distribuidas**.  
Este servicio se encarga de gestionar los **planos** y la **fabricación** de productos a partir de solicitudes de otros módulos (Inventario, Ventas, etc.).

## Arquitectura general

- Backend: **FastAPI** (Python)
- Base de datos: **PostgreSQL** (contenedor Docker)
- ORM: **SQLAlchemy**
- Esquema principal de la BD de Fabricación:
  - `piezas`: catálogo de piezas
  - `planos`: diseños de productos
  - `pieza_plano`: relación N–M entre planos y piezas (con cantidad)
  - `ordenes_fabricacion` (opcional): órdenes internas de fabricación

Este servicio está pensado para correr en contenedores y poder escalarse (varias “fábricas” en paralelo).

---

## Requisitos

- **Python 3.14** (o compatible)
- **Docker Desktop** instalado y corriendo
- Git (para clonar el repositorio)

---

## 1. Clonar el repositorio

```bash
git clone https://github.com/CarlosLte4/fabricacion-api

