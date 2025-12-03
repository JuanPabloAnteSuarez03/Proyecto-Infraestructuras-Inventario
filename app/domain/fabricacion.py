FABRICACION_PLAN = {
    "S1": {
        "piezas": [
            {"id_pieza": "P1", "cantidad": 2},
            {"id_pieza": "P2", "cantidad": 1},
        ],
        "tiempo_produccion": 3,
    },
    "S2": {
        "piezas": [
            {"id_pieza": "P3", "cantidad": 1},
            {"id_pieza": "P4", "cantidad": 2},
        ],
        "tiempo_produccion": 4,
    },
}


def obtener_plan(codigo: str) -> dict:
    codigo = codigo.upper()
    if codigo not in FABRICACION_PLAN:
        raise ValueError(f"No existe plan de fabricación para {codigo}")
    return FABRICACION_PLAN[codigo]
