"""Automatic power control (servo) on the regulating rod."""

from __future__ import annotations


class PowerServo:
    """Drives the regulating rod in or out at its fixed motor speed to hold a power setpoint.

    The servo works from the linear channel, like PUR-1's channel 3 servo. A
    lead term on the measured rate of change keeps it from overshooting.
    """

    def __init__(self, deadband: float = 0.005, lead_s: float = 12.0):
        self.enabled = False
        self.setpoint_w = 0.0
        self.deadband = deadband
        self.lead_s = lead_s
        self.error = 0.0
        self.captured = False  # True once power has settled near the setpoint

    @property
    def deviation(self) -> float | None:
        """Error used for the deviation alarm, only once the servo has captured the setpoint."""
        return self.error if (self.enabled and self.captured) else None

    def command(self, measured_w: float, log_rate: float) -> int:
        """Return -1 (in), 0 (stop) or +1 (out) for the regulating rod drive."""
        if not self.enabled or self.setpoint_w <= 0:
            return 0
        self.error = (self.setpoint_w - measured_w) / self.setpoint_w
        if abs(self.error) < 0.02:
            self.captured = True
        predicted = self.error - self.lead_s * log_rate * measured_w / self.setpoint_w
        if predicted > self.deadband:
            return 1
        if predicted < -self.deadband:
            return -1
        return 0
