"""Control rods with S-shaped worth curves, motor drives and gravity scram.

Positions are in cm withdrawn from the fully inserted (bottom) position.

A scrammable rod hangs from its drive by an electromagnet. On a scram the magnet
releases and the rod falls under gravity, reaching the bottom in ``drop_time``
from full withdrawal, while the drive stays where it was. The rod can be
withdrawn again only after the drive is run back down to the rod and the
magnet re-latches.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def integral_worth_fraction(x: float, length: float) -> float:
    """Fraction of total worth removed when withdrawn ``x`` of ``length`` (the classic S-curve)."""
    z = min(max(x / length, 0.0), 1.0)
    return z - math.sin(2 * math.pi * z) / (2 * math.pi)


@dataclass
class RodSpec:
    name: str
    worth: float  # total worth, dk/k (positive number)
    length_cm: float
    speed_cm_s: float
    scrammable: bool
    drop_time_s: float = 0.6


@dataclass
class Rod:
    spec: RodSpec
    position: float = 0.0  # rod position, cm withdrawn
    drive_position: float = 0.0  # drive mechanism position, cm
    latched: bool = True  # magnet holding the rod to its drive
    magnet_power: bool = True  # False while a scram is in effect
    command: int = 0  # -1 drive in, 0 stop, +1 drive out
    falling: bool = False
    fall_velocity: float = 0.0
    stuck: bool = False  # fault: rod will not move (including on scram)
    runaway: bool = False  # fault: drive withdraws regardless of command
    target: float | None = field(default=None)  # optional automatic drive-to position

    @property
    def name(self) -> str:
        return self.spec.name

    def inserted_worth(self) -> float:
        """Negative reactivity this rod currently holds in the core."""
        return self.spec.worth * (1.0 - integral_worth_fraction(self.position, self.spec.length_cm))

    def differential_worth(self) -> float:
        """d(rho)/dx in dk/k per cm at the current position."""
        L = self.spec.length_cm
        z = min(max(self.position / L, 0.0), 1.0)
        return self.spec.worth * (1 - math.cos(2 * math.pi * z)) / L

    def release(self) -> None:
        """Scram: de-energize the magnet."""
        if not self.spec.scrammable:
            return
        self.magnet_power = False
        if self.latched:
            self.latched = False
            if not self.stuck:
                self.falling = True
                self.fall_velocity = 0.0

    def advance(self, h: float) -> None:
        s = self.spec
        L = s.length_cm
        cmd = 1 if self.runaway else self.command
        if self.target is not None and not self.runaway:
            err = self.target - self.drive_position
            if abs(err) <= s.speed_cm_s * h:
                cmd = 0
                self.drive_position = min(max(self.target, 0.0), L)
                self.target = None
            else:
                cmd = 1 if err > 0 else -1
        if not self.stuck or not self.latched:
            self.drive_position = min(max(self.drive_position + cmd * s.speed_cm_s * h, 0.0), L)

        if self.latched:
            if not self.stuck:
                self.position = self.drive_position
            return

        if self.falling:
            accel = 2 * L / s.drop_time_s ** 2
            self.fall_velocity += accel * h
            self.position = max(self.position - self.fall_velocity * h, 0.0)
            if self.position <= 0.0:
                self.falling = False
                self.fall_velocity = 0.0
        # Re-latch once the drive has been run down to the (now bottomed) rod.
        if self.magnet_power and not self.falling and self.drive_position <= self.position + 0.05:
            self.latched = True
            self.position = self.drive_position
