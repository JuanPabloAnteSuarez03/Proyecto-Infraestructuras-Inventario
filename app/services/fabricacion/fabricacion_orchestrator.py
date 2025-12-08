import logging
import os
import time
from sqlalchemy.orm import Session
from app.services.fabricacion.fabricacion_service import FabricacionService
from app.services.fabricacion.ordenes_service import OrdenesFabricacionService
from app.services.proveedores.proveedores_service import ProveedoresService
from app.services.proveedores.solicitudes_service import SolicitudesPiezaService
from app.repositories import InventarioPiezasRepository
from app.models import InventarioPieza


class FabricacionOrchestrator:
    """Orquestador del flujo de creación de órdenes de fabricación."""

    def __init__(self, session: Session, fabricacion_service: FabricacionService | None = None) -> None:
        self.session = session
        self.fabricacion_service = fabricacion_service or FabricacionService()
        self.ordenes_service = OrdenesFabricacionService(session)
        self.piezas_repo = InventarioPiezasRepository(session)
        self.proveedores_service = ProveedoresService(session, piezas_repository=self.piezas_repo)
        self.solicitudes_service = SolicitudesPiezaService(session)
        self.log = logging.getLogger(self.__class__.__name__)
        try:
            delay = float(os.getenv("VISUAL_CONSUMO_DELAY", "5"))
        except ValueError:
            delay = 5.0
        self.consumo_delay = max(0.0, min(delay, 10.0))

    def crear_orden(self, codigo: str, cantidad: int) -> dict:
        detalle: dict[str, list | dict | str | int | bool] = {
            "pasos": [],
            "solicitudes_piezas": [],
            "consumo_piezas": [],
            "consumido_en_orquestador": True,
        }
        orden = self.ordenes_service.create(
            {"id_producto": codigo, "cantidad": cantidad, "estado": "calculando"}
        )

        try:
            detalle["pasos"].append("Calculando piezas necesarias (plan interno)...")
            plan_base = self.fabricacion_service.obtener_plan_base(codigo)
            materiales = [
                {"id_pieza": item["id_pieza"], "cantidad": item["cantidad"] * cantidad}
                for item in plan_base.get("piezas", [])
            ]
            tiempo_produccion = plan_base.get("tiempo_produccion", 0) * max(cantidad // 1, 1)
            detalle["plan"] = {
                "materiales": materiales,
                "tiempo_produccion": tiempo_produccion,
            }
            detalle["pasos"].append(f"Se necesitan {len(materiales)} tipos de piezas")

            detalle["pasos"].append("Verificando inventario de piezas, solicitando faltantes y consumiendo...")
            tiempo_reabastecimiento = 0

            for material in materiales:
                pieza = (
                    self.session.query(InventarioPieza)
                    .filter_by(id_pieza=material["id_pieza"])
                    .with_for_update()
                    .first()
                )
                disponible = pieza.cantidad if pieza else 0
                necesario = material["cantidad"]

                if disponible < necesario:
                    faltante = necesario - disponible
                    detalle["pasos"].append(f"Pieza {material['id_pieza']}: faltan {faltante} unidades, solicitando y reabasteciendo...")
                    proveedor = pieza.proveedor if pieza else None
                    eta = proveedor.tiempo if proveedor else 0

                    # Registrar solicitud async para que aparezca en dashboard
                    solicitud = self.solicitudes_service.create(
                        {
                            "id_pieza": material["id_pieza"],
                            "cantidad": faltante,
                            "estado": "en_proceso",
                            "tiempo_estimado": eta,
                        }
                    )

                    res = self.proveedores_service.solicitar_piezas(material["id_pieza"], faltante)
                    tiempo_reabastecimiento = max(
                        tiempo_reabastecimiento,
                        (res or {}).get("tiempo_entrega", eta),
                    )
                    self.session.refresh(pieza)

                    # Marcar solicitud como completada tras el reabastecimiento simulado
                    self.solicitudes_service.update(
                        solicitud.id,
                        {"estado": "completada", "tiempo_estimado": tiempo_reabastecimiento},
                    )

                    detalle["solicitudes_piezas"].append(
                        {
                            "id": solicitud.id,
                            "id_pieza": material["id_pieza"],
                            "cantidad": faltante,
                            "tiempo_entrega": tiempo_reabastecimiento,
                            "estado": "completada",
                        }
                    )
                    if self.consumo_delay > 0:
                        time.sleep(self.consumo_delay)

                consumo = min(pieza.cantidad if pieza else 0, necesario)
                if pieza:
                    pieza.cantidad = max(pieza.cantidad - consumo, 0)
                detalle["consumo_piezas"].append(
                    {
                        "id_pieza": material["id_pieza"],
                        "consumido": consumo,
                        "requerido": necesario,
                        "restante": pieza.cantidad if pieza else 0,
                    }
                )
                self.session.commit()

            detalle["pasos"].append("Enviando confirmación a fábrica externa (tras consumir piezas)...")
            orden.estado = "confirmando"
            self.session.commit()

            confirmacion = self.fabricacion_service.confirmar_fabricacion_externa(
                codigo, cantidad
            )

            if confirmacion and confirmacion.get("status") == "ok":
                orden.estado = "esperando_fabricacion"
                detalle["pasos"].append("✓ Fábrica externa confirmó la orden")
                detalle["confirmacion_fabrica"] = confirmacion
                detalle["fabricacion_externa"] = True
                self.log.info("Orden %s confirmada en fábrica externa", orden.id)
            else:
                orden.estado = "confirmacion_fallida"
                detalle["pasos"].append("✗ Fábrica externa no disponible")
                detalle["pasos"].append("No se permite fabricación local - orden marcada como fallida")
                detalle["fabricacion_externa"] = False
                self.log.warning("Orden %s sin confirmación externa, marcada como fallida", orden.id)

            orden.tiempo_estimado = tiempo_reabastecimiento + tiempo_produccion
            orden.detalle = detalle
            self.session.commit()

            return {
                "id": orden.id,
                "estado": orden.estado,
                "tiempo_estimado": orden.tiempo_estimado,
                "detalle": detalle,
            }

        except Exception as exc:  # pylint: disable=broad-except
            orden.estado = "fallida"
            orden.detalle = {"error": str(exc), "pasos": detalle.get("pasos", [])}
            self.session.commit()
            raise
