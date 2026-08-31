from __future__ import annotations

def apply_op(name: str, value: int, definitions: dict[str, dict[str, int]]) -> int:
    p = definitions[name]
    return value * p["a"] + p["b"]

def apply_procedure(value: int, procedure: list[str], definitions: dict[str, dict[str, int]]) -> int:
    for op in procedure:
        value = apply_op(op, value, definitions)
    return value
