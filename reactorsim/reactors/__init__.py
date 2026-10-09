"""Reactor designs. Add a new reactor by writing a module that defines a ``ReactorDesign``."""

from __future__ import annotations

from reactorsim.reactors.base import ReactorDesign
from reactorsim.reactors import pur1

_DESIGNS: dict[str, ReactorDesign] = {pur1.DESIGN.key: pur1.DESIGN}


def get_design(key: str) -> ReactorDesign:
    try:
        return _DESIGNS[key]
    except KeyError:
        raise KeyError(f"unknown reactor {key!r}; available: {sorted(_DESIGNS)}") from None


def list_designs() -> list[ReactorDesign]:
    return list(_DESIGNS.values())
