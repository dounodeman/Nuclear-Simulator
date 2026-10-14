"""Boiling water reactor plant model: pressurized vessel, recirculation, steam and feed systems."""

from reactorsim.bwr.design import BWRDesign

__all__ = ["BWRDesign"]


def __getattr__(name):
    if name == "BWRSimulator":
        from reactorsim.bwr.simulator import BWRSimulator
        return BWRSimulator
    raise AttributeError(name)
