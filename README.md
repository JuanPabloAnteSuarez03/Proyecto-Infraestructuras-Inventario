# Inventarios + Fabricación

API FastAPI para inventario de productos/piezas, órdenes de fabricación (con webhooks) y solicitudes a proveedores. Para detalles, ver la documentación en `docs/`.

- Código principal en `app/` (routers en `app/api`, servicios por dominio en `app/services/*`, repos en `app/repositories`).
- Artefactos de la fábrica simulada quedaron en `external/`.
- Dashboard de monitoreo: `dashboard.html`.
- Docker Compose expone la API en `http://localhost:5050` (uvicorn en 5000 dentro del contenedor).

Documentación ampliada: `docs/README.md` y `docs/ARCHITECTURE.md`.
