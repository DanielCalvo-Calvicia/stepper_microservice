import json
import os
from collections.abc import Mapping
from dataclasses import dataclass

_DEFAULT_STEPPERS = '{"stepper_1": {"step": 17, "dir": 27, "en": 5}}'


@dataclass(slots=True, frozen=True)
class StepperPins:
    """BCM pin numbers of one TMC2209 driver."""

    step_pin: int
    dir_pin: int
    en_pin: int


@dataclass(slots=True, frozen=True)
class StepperConfig:
    steppers: Mapping[str, StepperPins]
    default_speed_limit: float
    steps_per_revolution: int
    mock_hardware: bool

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "StepperConfig":
        raw = json.loads(env.get("STEPPER_CONFIGS", _DEFAULT_STEPPERS))
        steppers = {
            stepper_id: StepperPins(step_pin=pins["step"], dir_pin=pins["dir"], en_pin=pins["en"])
            for stepper_id, pins in raw.items()
        }
        steps_per_revolution = int(env.get("STEPS_PER_REVOLUTION", "400"))
        if steps_per_revolution <= 0:
            raise ValueError("STEPS_PER_REVOLUTION must be greater than 0")
        return cls(
            steppers=steppers,
            default_speed_limit=float(env.get("DEFAULT_SPEED_LIMIT", "1000.0")),
            steps_per_revolution=steps_per_revolution,
            mock_hardware=env.get("MOCK_HARDWARE", "0") == "1",
        )
