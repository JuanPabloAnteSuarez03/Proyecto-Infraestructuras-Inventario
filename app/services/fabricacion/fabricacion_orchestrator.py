import logging
from sqlalchemy.orm import Session
from app.services.fabricacion.fabricacion_service import FabricacionService
from app.services.fabricacion.ordenes_service import OrdenesFabricacionService
from app.services.proveedores.proveedores_service import ProveedoresService
from app.repositories import InventarioPiezasRepository


class FabricacionOrchestrator:
    """Orquestador del flujo de creación de órdenes de fabricación."""

    def __init__(self, session: Session, fabricacion_service: FabricacionService | None = None) -> None:
        self.session = session
        self.fabricacion_service = fabricacion_service or FabricacionService()
        self.ordenes_service = OrdenesFabricacionService(session)
        self.piezas_repo = InventarioPiezasRepository(session)
        self.proveedores_service = ProveedoresService(session, piezas_repository=self.piezas_repo)
        self.log = logging.getLogger(self.__class__.__name__)

    def crear_orden(self, codigo: str, cantidad: int) -> dict:
        detalle: dict[str, list | dict | str | int | bool] = {"pasos": []}
        orden = self.ordenes_service.create(
            {"id_producto": codigo, "cantidad": cantidad, "estado": "calculando"}
        )

        try:
            detalle["pasos"].append("Calculando piezas necesarias...")
            plan = self.fabricacion_service.solicitar_plan(codigo, cantidad)
            detalle["plan"] = {
                "materiales": plan.materiales,
                "tiempo_produccion": plan.tiempo_produccion,
            }
            detalle["pasos"].append(f"Se necesitan {len(plan.materiales)} tipos de piezas")

            detalle["pasos"].append("Verificando inventario de piezas...")
            tiempo_reabastecimiento = 0

            for material in plan.materiales:
                pieza = self.piezas_repo.get_by_id(material["id_pieza"])
                disponible = pieza.cantidad if pieza else 0
                necesario = material["cantidad"]

                if disponible < necesario:
                    faltante = necesario - disponible
                    detalle["pasos"].append(f"Pieza {material['id_pieza']}: faltan {faltante} unidades")
                    resultado_proveedor = self.proveedores_service.solicitar_piezas(
                        material["id_pieza"], faltante
                    )
                    tiempo_reabastecimiento = max(
                        tiempo_reabastecimiento, resultado_proveedor["tiempo_entrega"]
                    )
                    detalle["pasos"].append(
                        f"Solicitado a proveedor: {faltante} x {material['id_pieza']}"
                    )

            self.session.commit()

            detalle["pasos"].append("Enviando confirmación a fábrica externa...")
            orden.estado = "confirmando"
            self.session.commit()

            confirmacion = self.fabricacion_service.confirmar_fabricacion_externa(
                codigo, cantidad
            )

            if confirmacion and confirmacion.get("status") == "ok":
                orden.estado = "confirmado"
                detalle["pasos"].append("✓ Fábrica externa confirmó la orden")
                detalle["confirmacion_fabrica"] = confirmacion
                detalle["fabricacion_externa"] = True
                self.log.info("Orden %s confirmada en fábrica externa", orden.id)

                from app.tasks import queue, procesar_orden_fabricacion  # import tardío para evitar ciclos
                queue.enqueue(procesar_orden_fabricacion, orden.id)
                detalle["pasos"].append("Worker encolado para consumir piezas y esperar productos")
            else:
                orden.estado = "confirmacion_fallida"
                detalle["pasos"].append("✗ Fábrica externa no disponible")
                detalle["pasos"].append("No se permite fabricación local - orden marcada como fallida")
                detalle["fabricacion_externa"] = False
                self.log.warning("Orden %s sin confirmación externa, marcada como fallida", orden.id)
                from app.tasks import queue, procesar_orden_fabricacion  # import tardío para evitar ciclos
                queue.enqueue(procesar_orden_fabricacion, orden.id)

            orden.tiempo_estimado = tiempo_reabastecimiento + plan.tiempo_produccion
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
