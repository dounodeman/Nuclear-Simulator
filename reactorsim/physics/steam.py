"""Saturated light-water properties for the pressurized-vessel models.

A small steam table (0.1 to 20 MPa) interpolated in log(pressure). Accurate to
about 0.3% against IAPWS-IF97 across the range, which is plenty for a lumped
vessel; the point is to get saturation temperature, latent heat and the steam
density derivative (which sets how fast a sealed vessel pressurizes) right.
"""

from __future__ import annotations

import numpy as np

# pressure MPa, Tsat C, h_f kJ/kg, h_g kJ/kg, rho_f kg/m3, rho_g kg/m3
_TABLE = np.array([
    [0.1, 99.6, 417.5, 2675.4, 958.6, 0.590],
    [0.2, 120.2, 504.7, 2706.2, 942.9, 1.129],
    [0.5, 151.8, 640.1, 2748.1, 915.3, 2.668],
    [1.0, 179.9, 762.6, 2777.1, 887.1, 5.145],
    [1.5, 198.3, 844.6, 2791.0, 866.6, 7.593],
    [2.0, 212.4, 908.5, 2798.3, 849.8, 10.04],
    [3.0, 233.9, 1008.3, 2803.2, 821.9, 15.00],
    [4.0, 250.4, 1087.4, 2800.8, 798.4, 20.09],
    [5.0, 263.9, 1154.5, 2794.2, 777.4, 25.35],
    [6.0, 275.6, 1213.7, 2784.6, 758.0, 30.82],
    [7.0, 285.8, 1267.4, 2772.6, 739.7, 36.53],
    [7.5, 290.5, 1292.7, 2765.9, 730.9, 39.48],
    [8.0, 295.0, 1317.1, 2758.7, 722.2, 42.51],
    [8.5, 299.3, 1340.7, 2751.0, 713.6, 45.61],
    [9.0, 303.3, 1363.7, 2742.9, 705.2, 48.79],
    [10.0, 311.0, 1407.8, 2725.5, 688.4, 55.46],
    [12.0, 324.7, 1491.3, 2685.4, 655.4, 70.10],
    [14.0, 336.7, 1571.0, 2637.9, 620.5, 87.05],
    [16.0, 347.4, 1649.7, 2580.8, 585.0, 107.4],
    [18.0, 357.0, 1732.0, 2509.5, 543.0, 133.6],
    [20.0, 365.7, 1827.2, 2411.4, 490.5, 170.6],
])
_LOGP = np.log(_TABLE[:, 0] * 1e6)
MPA = 1e6
PSI = 6894.757


def _col(i: int, pressure_pa: float) -> float:
    return float(np.interp(np.log(max(pressure_pa, 1e5)), _LOGP, _TABLE[:, i]))


def t_sat(pressure_pa: float) -> float:
    """Saturation temperature, C."""
    return _col(1, pressure_pa)


def h_f(pressure_pa: float) -> float:
    """Saturated liquid enthalpy, J/kg."""
    return _col(2, pressure_pa) * 1e3


def h_g(pressure_pa: float) -> float:
    """Saturated vapour enthalpy, J/kg."""
    return _col(3, pressure_pa) * 1e3


def h_fg(pressure_pa: float) -> float:
    return h_g(pressure_pa) - h_f(pressure_pa)


def rho_f(pressure_pa: float) -> float:
    return _col(4, pressure_pa)


def rho_g(pressure_pa: float) -> float:
    return _col(5, pressure_pa)


def drho_g_dp(pressure_pa: float) -> float:
    """d(rho_g)/dp, kg/m3 per Pa, by central difference on the table."""
    dp = 0.01 * pressure_pa
    return (rho_g(pressure_pa + dp) - rho_g(pressure_pa - dp)) / (2 * dp)


def dt_sat_dp(pressure_pa: float) -> float:
    """d(Tsat)/dp, K per Pa."""
    dp = 0.01 * pressure_pa
    return (t_sat(pressure_pa + dp) - t_sat(pressure_pa - dp)) / (2 * dp)


def h_liquid(temp_c: float, pressure_pa: float) -> float:
    """Enthalpy of subcooled liquid: saturated enthalpy less cp times the subcooling (J/kg)."""
    return h_f(pressure_pa) - 4800.0 * (t_sat(pressure_pa) - temp_c)


def psig(pressure_pa: float) -> float:
    return (pressure_pa - 101325.0) / PSI


def from_psig(p: float) -> float:
    return p * PSI + 101325.0
