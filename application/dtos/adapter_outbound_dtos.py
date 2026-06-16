from dataclasses import dataclass
from typing import Any

@dataclass(slots=True, frozen=True)
class StepperConfigDto:
    """Individual configuration for a single stepper."""
    step_pin: int
    dir_pin: int
    en_pin: int

@dataclass(slots=True, frozen=True)
class InitOutboundAdapterDto:
    """Configures the hardware motor driver adapter with multiple steppers."""
    steppers: dict[str, StepperConfigDto]
    default_max_speed: float = 1000.0


@dataclass(slots=True, frozen=True)
class MotorCommandDto:
    """Concrete command instructions sent to the hardware layer."""
    stepper_id: str
    action: str  # 'steps', 'stop'
    steps: int = 0
    speed_steps_per_sec: float = 0.0
    forward: bool = True

@dataclass(slots=True, frozen=True)
class MotorStatusDto:
    """Response from hardware layer indicating outcome."""
    success: bool
    message: str
