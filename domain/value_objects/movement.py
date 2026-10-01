from dataclasses import dataclass

from domain.errors import InvalidMovement


@dataclass(slots=True, frozen=True)
class Movement:
    """A resolved movement of one motor: how many steps, how fast, which way.

    Invariant: ``steps`` is not negative and ``speed_steps_per_second`` is strictly positive.
    """

    steps: int
    speed_steps_per_second: float
    forward: bool

    def __post_init__(self) -> None:
        if self.steps < 0:
            raise InvalidMovement("The number of steps cannot be negative.")
        if self.speed_steps_per_second <= 0:
            raise InvalidMovement("Speed must be greater than 0.")
