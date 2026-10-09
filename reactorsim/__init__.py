"""reactorsim: a physics-first nuclear reactor simulator.

The engine is split into reusable physics models (``reactorsim.physics``),
plant systems such as rods, instruments and protection logic
(``reactorsim.plant``), and reactor definitions (``reactorsim.reactors``).
``reactorsim.simulator.Simulator`` ties them together.
"""

import os

# The kinetics solve is a matrix exponential of an 8 x 8 matrix every step. Multithreaded BLAS
# only adds overhead at that size, and its spinning threads slow the live control room badly
# when anything else is busy, so default to one thread unless the user chose otherwise.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

from reactorsim.simulator import Simulator  # noqa: E402
from reactorsim.reactors import get_design, list_designs  # noqa: E402

__all__ = ["Simulator", "get_design", "list_designs"]
__version__ = "0.1.0"
