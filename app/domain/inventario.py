from __future__ import annotations

PRODUCT_CODES: tuple[str, ...] = ("S1", "S2")
PRODUCT_STATES: tuple[str, ...] = ("Reservado", "A Despacho", "Disponible", "Pendiente")

_PRODUCT_LOOKUP = {code.lower(): code for code in PRODUCT_CODES}
_STATE_LOOKUP = {state.lower(): state for state in PRODUCT_STATES}


def normalize_producto_codigo(value: str) -> str:
    key = (value or "").strip().lower()
    if key not in _PRODUCT_LOOKUP:
        raise ValueError("Producto no permitido. Solo S1 o S2")
    return _PRODUCT_LOOKUP[key]


def normalize_estado(value: str) -> str:
    key = (value or "").strip().lower()
    if key not in _STATE_LOOKUP:
        raise ValueError(
            "Estado no permitido. Use Reservado, A Despacho, Disponible o Pendiente"
        )
    return _STATE_LOOKUP[key]
