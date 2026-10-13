"""Reactor designs. Add a new reactor by writing a module that defines a design object.

Two families of design exist: ``ReactorDesign`` (open-pool reactors, run by
``reactorsim.Simulator``) and ``BWRDesign`` (boiling water reactors, run by
``reactorsim.bwr.BWRSimulator``). ``simulator_for`` picks the right engine.
"""

from __future__ import annotations

from reactorsim.reactors.base import ReactorDesign
from reactorsim.reactors import peach_bottom_2, pur1

_DESIGNS: dict = {pur1.DESIGN.key: pur1.DESIGN, peach_bottom_2.DESIGN.key: peach_bottom_2.DESIGN}


def get_design(key: str):
    try:
        return _DESIGNS[key]
    except KeyError:
        raise KeyError(f"unknown reactor {key!r}; available: {sorted(_DESIGNS)}") from None


def list_designs() -> list:
    return list(_DESIGNS.values())


def design_kind(design) -> str:
    """'pool' for a ``ReactorDesign``, otherwise the design's own ``kind`` (e.g. 'bwr')."""
    return "pool" if isinstance(design, ReactorDesign) else getattr(design, "kind", "unknown")


def simulator_for(key: str, **kwargs):
    """Build the simulator that runs the design ``key``."""
    d = get_design(key)
    if design_kind(d) == "bwr":
        from reactorsim.bwr.simulator import BWRSimulator
        return BWRSimulator(d, **kwargs)
    from reactorsim.simulator import Simulator
    return Simulator(d, **kwargs)
