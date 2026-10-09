"""reactorsim: a physics-first nuclear reactor simulator.

The engine is split into reusable physics models (``reactorsim.physics``),
plant systems such as rods, instruments and protection logic
(``reactorsim.plant``), and reactor definitions (``reactorsim.reactors``).
``reactorsim.simulator.Simulator`` ties them together.
"""

from reactorsim.simulator import Simulator
from reactorsim.reactors import get_design, list_designs

__all__ = ["Simulator", "get_design", "list_designs"]
__version__ = "0.1.0"
