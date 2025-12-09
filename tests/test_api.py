from typing import Iterable


def crear_estados_producto(client, codigo: str, estados: Iterable[str] | None = None):
    estados = estados or ["Reservado", "A Despacho", "Disponible"]
    for estado in estados:
        resp = client.post(
            "/api/productos",
            json={"id_producto": codigo, "estado": estado, "cantidad": 0},
        )
        assert resp.status_code == 201


def test_productos_transfer_flow(client):
    crear_estados_producto(client, "S1")

    listado = client.get("/api/productos")
    assert listado.status_code == 200
    assert len(listado.json()) == 3

    disponible_update = client.put(
        "/api/productos/S1/Disponible", json={"cantidad": 120}
    )
    assert disponible_update.status_code == 200

    transfer_resp = client.post(
        "/api/productos/transferencias",
        json={
            "id_producto": "S1",
            "estado_origen": "Disponible",
            "estado_destino": "Reservado",
            "cantidad": 50,
        },
    )
    assert transfer_resp.status_code == 200
    estados = {item["estado"]: item["cantidad"] for item in transfer_resp.json()}
    assert estados["Disponible"] == 70
    assert estados["Reservado"] == 50

    segundo_transfer = client.post(
        "/api/productos/transferencias",
        json={
            "id_producto": "S1",
            "estado_origen": "Reservado",
            "estado_destino": "A Despacho",
            "cantidad": 20,
        },
    )
    assert segundo_transfer.status_code == 200
    estados = {item["estado"]: item["cantidad"] for item in segundo_transfer.json()}
    assert estados["Reservado"] == 30
    assert estados["A Despacho"] == 20

    insufficient_transfer = client.post(
        "/api/productos/transferencias",
        json={
            "id_producto": "S1",
            "estado_origen": "Reservado",
            "estado_destino": "Disponible",
            "cantidad": 999,
        },
    )
    assert insufficient_transfer.status_code == 400

    reserva = client.post(
        "/api/productos/reservas",
        json={"id_producto": "S1", "cantidad": 20},
    )
    assert reserva.status_code == 200
    data = reserva.json()
    assert data["reservado"] is True
    assert data["cantidad_confirmada"] == 20
    assert data["cantidad_pendiente"] == 0
    assert data["tiempo_estimado"] >= 0
    assert data["cantidad_disponible"] == 50
    assert data["estado_ingreso"] == "Reservado"

    reserva_insuficiente = client.post(
        "/api/productos/reservas",
        json={"id_producto": "S1", "cantidad": 5000},
    )
    assert reserva_insuficiente.status_code == 200
    data = reserva_insuficiente.json()
    assert data["reservado"] is True
    assert data["cantidad_confirmada"] == 5000
    assert data["cantidad_pendiente"] == 0
    assert data["tiempo_estimado"] >= 0
    assert data["estado_ingreso"] == "A Despacho"
    assert data["fabricado"] is True

    despacho_desde_fabrica = client.post(
        "/api/productos/despachos",
        json={"id_producto": "S1", "cantidad": 999},
    )
    assert despacho_desde_fabrica.status_code == 200
    data = despacho_desde_fabrica.json()
    assert data["despachado"] is True
    assert data["cantidad_confirmada"] == 999
    assert data["cantidad_pendiente"] == 0
    assert data["tiempo_estimado"] >= 0
    assert data["estado_ingreso"] == "A Despacho"

    despacho_ok = client.post(
        "/api/productos/despachos",
        json={"id_producto": "S1", "cantidad": 20},
    )
    assert despacho_ok.status_code == 200
    data = despacho_ok.json()
    assert data["despachado"] is True
    assert data["cantidad_confirmada"] == 20
    assert data["estado_ingreso"] == "A Despacho"
    assert data["cantidad_pendiente"] == 0
    assert data["tiempo_estimado"] == 0


def test_incrementar_productos(client):
    crear_estados_producto(client, "S1")

    primer_ingreso = client.post(
        "/api/productos/ingresos",
        json={"id_producto": "S1", "cantidad": 40},
    )
    assert primer_ingreso.status_code == 200
    data = primer_ingreso.json()
    assert data["estado"] == "Disponible"
    assert data["cantidad"] == 40

    segundo_ingreso = client.post(
        "/api/productos/ingresos",
        json={"id_producto": "S1", "cantidad": 10},
    )
    assert segundo_ingreso.status_code == 200
    data = segundo_ingreso.json()
    assert data["cantidad"] == 50

    ingreso_reservado = client.post(
        "/api/productos/ingresos",
        json={"id_producto": "S1", "estado": "Reservado", "cantidad": 5},
    )
    assert ingreso_reservado.status_code == 200
    data = ingreso_reservado.json()
    assert data["estado"] == "Reservado"
    assert data["cantidad"] == 5

    ingreso_invalido = client.post(
        "/api/productos/ingresos",
        json={"id_producto": "S1", "estado": "invalido", "cantidad": 5},
    )
    assert ingreso_invalido.status_code == 400


def test_listar_productos_pendientes(client):
    crear_estados_producto(client, "S1", ["Pendiente"])
    crear_estados_producto(client, "S2", ["Pendiente", "Disponible"])

    resp1 = client.put("/api/productos/S1/Pendiente", json={"cantidad": 7})
    resp2 = client.put("/api/productos/S2/Pendiente", json={"cantidad": 3})
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    listado = client.get("/api/productos/pendientes")
    assert listado.status_code == 200
    data = listado.json()
    assert len(data) == 2
    assert all(item["estado"] == "Pendiente" for item in data)
    cantidades = {(item["id_producto"], item["estado"]): item["cantidad"] for item in data}
    assert cantidades[("S1", "Pendiente")] == 7
    assert cantidades[("S2", "Pendiente")] == 3


def test_descontar_pendiente_y_despacho(client):
    crear_estados_producto(client, "S1", ["Pendiente", "A Despacho"])

    set_pendiente = client.put("/api/productos/S1/Pendiente", json={"cantidad": 10})
    set_despacho = client.put("/api/productos/S1/A Despacho", json={"cantidad": 5})
    assert set_pendiente.status_code == 200
    assert set_despacho.status_code == 200

    restar_pendiente = client.post(
        "/api/productos/pendientes/descontar",
        json={"id_producto": "S1", "cantidad": 4},
    )
    restar_despacho = client.post(
        "/api/productos/despachos/descontar",
        json={"id_producto": "S1", "cantidad": 2},
    )
    assert restar_pendiente.status_code == 200
    assert restar_despacho.status_code == 200
    assert restar_pendiente.json()["cantidad"] == 6
    assert restar_despacho.json()["cantidad"] == 3

    insuficiente = client.post(
        "/api/productos/pendientes/descontar",
        json={"id_producto": "S1", "cantidad": 999},
    )
    assert insuficiente.status_code == 400


def test_retiro_consumiendo_reservado_y_disponible(client):
    crear_estados_producto(client, "S1", ["Reservado", "Disponible"])
    resp_res = client.put("/api/productos/S1/Reservado", json={"cantidad": 3})
    resp_disp = client.put("/api/productos/S1/Disponible", json={"cantidad": 10})
    assert resp_res.status_code == 200
    assert resp_disp.status_code == 200

    retiro = client.post(
        "/api/productos/retiros", json={"id_producto": "S1", "cantidad": 5}
    )
    assert retiro.status_code == 200
    data = retiro.json()
    assert data["reservado_restante"] == 0
    assert data["disponible_restante"] == 8

    insuficiente = client.post(
        "/api/productos/retiros", json={"id_producto": "S1", "cantidad": 20}
    )
    assert insuficiente.status_code == 400


def test_proveedores_y_piezas_flow(client):
    proveedor_resp = client.post(
        "/api/proveedores",
        json={
            "id_proveedor": 99,
            "nombre": "Proveedor Especial",
            "cantidad": 100,
            "tiempo": 5,
        },
    )
    assert proveedor_resp.status_code == 201

    provider_update = client.put(
        "/api/proveedores/99", json={"nombre": "Proveedor Prime"}
    )
    assert provider_update.status_code == 200
    assert provider_update.json()["nombre"] == "Proveedor Prime"

    pieza_resp = client.post(
        "/api/piezas",
        json={"id_pieza": "PX1", "cantidad": 50, "id_proveedor": 99},
    )
    assert pieza_resp.status_code == 201

    pieza_update = client.put("/api/piezas/PX1", json={"cantidad": 75})
    assert pieza_update.status_code == 200
    assert pieza_update.json()["cantidad"] == 75

    get_piezas = client.get("/api/piezas")
    assert get_piezas.status_code == 200
    assert len(get_piezas.json()) >= 3

    delete_pieza = client.delete("/api/piezas/PX1")
    assert delete_pieza.status_code == 200

    delete_proveedor = client.delete("/api/proveedores/99")
    assert delete_proveedor.status_code == 200

    solicitud = client.post(
        "/api/proveedores/solicitudes",
        json={"id_pieza": "P1", "cantidad": 150},
    )
    assert solicitud.status_code == 200
    data = solicitud.json()
    assert data["cantidad_recibida"] == 150
    pieza_actualizada = client.get("/api/piezas/P1")
    assert pieza_actualizada.status_code == 200
    assert pieza_actualizada.json()["cantidad"] == 150


def test_movimientos_flow(client):
    create_resp = client.post(
        "/api/movimientos",
        json={
            "id_movimiento": 1,
            "id_objeto": 1,
            "tipo_objeto": "producto",
            "cantidad": 10,
            "direccion": "entrada",
        },
    )
    assert create_resp.status_code == 201

    update_resp = client.put("/api/movimientos/1", json={"direccion": "salida"})
    assert update_resp.status_code == 200
    assert update_resp.json()["direccion"] == "salida"

    get_resp = client.get("/api/movimientos/1")
    assert get_resp.status_code == 200

    delete_resp = client.delete("/api/movimientos/1")
    assert delete_resp.status_code == 200

    missing_resp = client.get("/api/movimientos/1")
    assert missing_resp.status_code == 404


def test_fabricacion_plan_y_produccion(client):
    crear_estados_producto(client, "S1")
    plan_resp = client.get("/api/fabricacion/plan/S1?cantidad=100")
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert plan_data["id_producto"] == "S1"
    assert plan_data["cantidad_solicitada"] == 100
    assert plan_data["materiales"]

    produccion_resp = client.post(
        "/api/fabricacion/producciones",
        json={"id_producto": "S1", "cantidad": 100},
    )
    assert produccion_resp.status_code == 200
    produccion_data = produccion_resp.json()
    assert produccion_data["cantidad_producida"] == 100
    inventario = client.get("/api/productos/S1").json()
    estados = {item["estado"]: item["cantidad"] for item in inventario}
    assert estados["Disponible"] >= 100


def test_calcular_piezas(client):
    resp = client.post(
        "/api/fabricacion/calcular_piezas",
        json={"codigo": "S1", "cantidad": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["codigo"] == "S1"
    assert data["cantidad_solicitada"] == 3
    piezas = {item["codigo"]: item for item in data["piezas"]}
    assert piezas["P1"]["cantidad_por_unidad"] == 1
    assert piezas["P1"]["cantidad_total"] == 3
    assert piezas["P2"]["cantidad_por_unidad"] == 1
    assert piezas["P2"]["cantidad_total"] == 3
    # Plan interno alineado con fábrica: P1..P6, 1 unidad cada uno
    assert piezas["P3"]["cantidad_por_unidad"] == 1
    assert piezas["P4"]["cantidad_por_unidad"] == 1
    assert piezas["P5"]["cantidad_por_unidad"] == 1
    assert piezas["P6"]["cantidad_por_unidad"] == 1

    resp_invalido = client.post(
        "/api/fabricacion/calcular_piezas",
        json={"codigo": "S1", "cantidad": 0},
    )
    assert resp_invalido.status_code == 400
