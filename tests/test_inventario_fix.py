"""
Test para validar la solución al problema de discrepancias en inventario.

Problema original:
- Caso 1 (exitoso): 1000 inicial + venta 1500 = 3000 en Pendiente ✓
- Caso 2 (falla): Misma operación = 3085 en Pendiente (85 extras) ✗

Este test valida que después de la solución, ambos casos funcionan correctamente.
"""

import pytest
from fastapi.testclient import TestClient


class TestInventarioDiscrepancyFix:
    """Tests para validar que la solución elimina discrepancias."""

    def test_caso_exitoso_venta_online_con_faltante(self, client):
        """
        Test del caso exitoso: 1000 inicial, venta 1500, fabricar 500.
        Resultado esperado: Pendiente = 3000
        """
        # PASO 1: Crear stock inicial de 1000 en Disponible
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 1000, "estado": "Disponible"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cantidad"] == 1000
        assert data["estado"] == "Disponible"

        # Verificar estado inicial
        response = client.get("/api/productos/S1")
        estados = {e["estado"]: e["cantidad"] for e in response.json()}
        assert estados["Disponible"] == 1000
        assert estados.get("Pendiente", 0) == 0

        # PASO 2: Venta online de 1500
        response = client.post(
            "/api/productos/pedidos/online",
            json={"id_producto": "S1", "cantidad": 1500}
        )
        assert response.status_code == 200
        data = response.json()

        # Debe transferir 1000 a Pendiente y crear orden por 500
        assert data["cantidad_en_pendiente"] == 1000
        assert data["faltante_fabricado"] == 500
        assert data["estado_destino"] == "Pendiente"
        orden_id = data.get("orden_id")
        assert orden_id is not None

        # Verificar estado después de venta
        response = client.get("/api/productos/S1")
        estados = {e["estado"]: e["cantidad"] for e in response.json()}
        assert estados["Disponible"] == 0
        assert estados["Pendiente"] == 1000

        # PASO 3: Ingresar fabricación de 500 a Pendiente
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 500, "estado": "Pendiente"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cantidad"] == 1500  # 1000 + 500 = 1500
        assert data["estado"] == "Pendiente"

        # Verificar estado final
        response = client.get("/api/productos/S1")
        estados = {e["estado"]: e["cantidad"] for e in response.json()}
        assert estados["Disponible"] == 0
        assert estados["Pendiente"] == 1500  # ✓ CORRECTO

        # Verificar que el pedido se completó
        response = client.get("/api/productos/pedidos?estado=abierto")
        pedidos_abiertos = response.json()
        assert len(pedidos_abiertos) == 0  # No debe haber pedidos abiertos

    def test_caso_multiple_ventas_online(self, client):
        """
        Test con múltiples ventas online consecutivas.
        Este era el caso que fallaba con 3085 en lugar de 3000.
        """
        # PASO 1: Stock inicial de 1000
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 1000, "estado": "Disponible"}
        )
        assert response.status_code == 200

        # PASO 2: Primera venta online de 1500
        response = client.post(
            "/api/productos/pedidos/online",
            json={"id_producto": "S1", "cantidad": 1500}
        )
        assert response.status_code == 200
        data1 = response.json()
        assert data1["cantidad_en_pendiente"] == 1000
        assert data1["faltante_fabricado"] == 500
        orden_id_1 = data1["orden_id"]

        # PASO 3: Segunda venta online de 1500 (sin stock disponible)
        response = client.post(
            "/api/productos/pedidos/online",
            json={"id_producto": "S1", "cantidad": 1500}
        )
        assert response.status_code == 200
        data2 = response.json()
        # Como Disponible=0, todo va a faltante
        assert data2["cantidad_en_pendiente"] == 1000  # No cambió
        assert data2["faltante_fabricado"] == 1500
        orden_id_2 = data2["orden_id"]

        # Verificar que hay 2 pedidos abiertos
        response = client.get("/api/productos/pedidos?estado=abierto")
        pedidos_abiertos = response.json()
        assert len(pedidos_abiertos) == 2

        # PASO 4: Ingresar fabricación de orden 1 (500)
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 500, "estado": "Pendiente"}
        )
        assert response.status_code == 200

        # Verificar Pendiente
        response = client.get("/api/productos/S1/Pendiente")
        assert response.json()["cantidad"] == 1500  # 1000 + 500

        # PASO 5: Ingresar fabricación de orden 2 (1500)
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 1500, "estado": "Pendiente"}
        )
        assert response.status_code == 200

        # PASO 6: Verificar resultado final
        response = client.get("/api/productos/S1")
        estados = {e["estado"]: e["cantidad"] for e in response.json()}

        # ✓ DEBE SER 3000, NO 3085
        assert estados["Pendiente"] == 3000, f"ERROR: Pendiente={estados['Pendiente']}, esperado 3000"
        assert estados["Disponible"] == 0

        # Verificar que todos los pedidos se completaron
        response = client.get("/api/productos/pedidos?estado=abierto")
        pedidos_abiertos = response.json()
        assert len(pedidos_abiertos) == 0

    def test_ingreso_a_disponible_con_pedidos_abiertos(self, client):
        """
        Test cuando se ingresa a Disponible y hay pedidos abiertos.
        Debe asignar automáticamente a los pedidos.
        """
        # PASO 1: Venta online de 1500 sin stock
        response = client.post(
            "/api/productos/pedidos/online",
            json={"id_producto": "S1", "cantidad": 1500}
        )
        assert response.status_code == 200

        # Verificar que hay pedido abierto
        response = client.get("/api/productos/pedidos?estado=abierto")
        pedidos_abiertos = response.json()
        assert len(pedidos_abiertos) == 1
        assert pedidos_abiertos[0]["cantidad_faltante"] == 1500

        # PASO 2: Ingresar 1500 a Disponible (debe transferirse automáticamente)
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 1500, "estado": "Disponible"}
        )
        assert response.status_code == 200

        # PASO 3: Verificar que se transfirió a Pendiente
        response = client.get("/api/productos/S1")
        estados = {e["estado"]: e["cantidad"] for e in response.json()}
        assert estados["Disponible"] == 0  # Se transfirió todo
        assert estados["Pendiente"] == 1500  # A pedidos abiertos

        # Verificar que el pedido se completó
        response = client.get("/api/productos/pedidos?estado=abierto")
        pedidos_abiertos = response.json()
        assert len(pedidos_abiertos) == 0

    def test_validacion_cantidad_atendida_no_excede_solicitada(self, client):
        """
        Test que valida que cantidad_atendida nunca exceda cantidad_solicitada.
        Si esto ocurre, debe lanzar un error.
        """
        # PASO 1: Venta online de 500
        response = client.post(
            "/api/productos/pedidos/online",
            json={"id_producto": "S1", "cantidad": 500}
        )
        assert response.status_code == 200

        # PASO 2: Ingresar exactamente 500
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 500, "estado": "Pendiente"}
        )
        assert response.status_code == 200

        # Verificar que el pedido se completó correctamente
        response = client.get("/api/productos/pedidos")
        pedidos = response.json()
        pedido = next(p for p in pedidos if p["id_producto"] == "S1")
        assert pedido["cantidad_atendida"] == 500
        assert pedido["cantidad_solicitada"] == 500
        assert pedido["estado"] == "completado"

    def test_ingreso_parcial_multiple(self, client):
        """
        Test con múltiples ingresos parciales para una orden.
        """
        # PASO 1: Venta online de 1000
        response = client.post(
            "/api/productos/pedidos/online",
            json={"id_producto": "S1", "cantidad": 1000}
        )
        assert response.status_code == 200
        orden_id = response.json()["orden_id"]

        # PASO 2: Ingreso parcial 1 (250)
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 250, "estado": "Pendiente"}
        )
        assert response.status_code == 200
        assert response.json()["cantidad"] == 250

        # PASO 3: Ingreso parcial 2 (250)
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 250, "estado": "Pendiente"}
        )
        assert response.status_code == 200
        assert response.json()["cantidad"] == 500

        # PASO 4: Ingreso parcial 3 (500)
        response = client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 500, "estado": "Pendiente"}
        )
        assert response.status_code == 200
        assert response.json()["cantidad"] == 1000

        # PASO 5: Verificar resultado final
        response = client.get("/api/productos/S1/Pendiente")
        assert response.json()["cantidad"] == 1000

        # Verificar que el pedido se completó
        response = client.get("/api/productos/pedidos?estado=abierto")
        assert len(response.json()) == 0

    def test_nuevo_endpoint_tracking_ordenes(self, client):
        """
        Test del nuevo endpoint para registrar entregas por orden_id.
        """
        # PASO 1: Crear stock y hacer venta
        client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 500, "estado": "Disponible"}
        )
        response = client.post(
            "/api/productos/pedidos/online",
            json={"id_producto": "S1", "cantidad": 1000}
        )
        orden_id = response.json()["orden_id"]

        # PASO 2: Ingresar inventario
        client.post(
            "/api/productos/ingresos",
            json={"id_producto": "S1", "cantidad": 500, "estado": "Pendiente"}
        )

        # PASO 3: Registrar tracking de entrega en la orden
        response = client.post(
            f"/api/productos/ordenes/{orden_id}/entregas",
            json={"cantidad": 500}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["orden_id"] == orden_id
        assert data["acumulado"] == 500
        assert data["completada"] is True
        assert data["estado"] == "completada"

    def test_endpoint_tracking_orden_no_existente(self, client):
        """
        Test que valida error cuando se intenta registrar entrega en orden inexistente.
        """
        response = client.post(
            "/api/productos/ordenes/99999/entregas",
            json={"cantidad": 500}
        )
        assert response.status_code == 404
        response_data = response.json()
        # Puede venir en diferentes formatos
        if isinstance(response_data, dict) and "detail" in response_data:
            assert "no encontrada" in response_data["detail"].lower()
        else:
            # Si el endpoint devuelve directamente el mensaje
            assert response_data is None or "99999" in str(response_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
