from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MotorCommandOutboundDTO:
    """What the motor driver is asked to do: a resolved movement of one motor."""

    stepper_id: str
    steps: int
    speed_steps_per_second: float
    forward: bool


@dataclass(slots=True, frozen=True)
class MotorStatusOutboundDTO:
    """What the motor driver reports back."""

    success: bool
    message: str
