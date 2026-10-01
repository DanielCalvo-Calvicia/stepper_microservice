"""Pure unit conversions and validation of a movement request."""

from domain.errors import InvalidMovement
from domain.value_objects.movement import Movement

ACTIONS = ("rotate", "steps", "stop")
_FORWARD = {"forward", "clockwise"}
_REVERSE = {"reverse", "counterclockwise"}


def is_forward(direction: str) -> bool:
    """``forward`` (or ``clockwise``) is forward, ``reverse`` (or ``counterclockwise``) is not."""
    value = direction.strip().lower()
    if value in _FORWARD:
        return True
    if value in _REVERSE:
        return False
    raise InvalidMovement(f"Unknown direction: {direction!r}. Use 'forward' or 'reverse'.")


def rotations_to_steps(rotations: float, steps_per_revolution: int) -> int:
    """STEP pulses for a number of full revolutions (full steps x microsteps).

    The sign is dropped: the travel direction is carried separately by ``direction``.
    """
    return int(abs(rotations) * steps_per_revolution)


def rpm_to_steps_per_second(rpm: float, steps_per_revolution: int) -> float:
    """RPM as steps per second. The sign is kept so a negative speed can still be rejected."""
    return rpm * steps_per_revolution / 60.0


def resolve_speed(requested_steps_per_second: float, default_max_steps_per_second: float) -> float:
    """A negative speed is rejected; zero means the default speed limit."""
    if requested_steps_per_second < 0:
        raise InvalidMovement("Speed must be a positive value.")
    if requested_steps_per_second == 0.0:
        return default_max_steps_per_second
    return requested_steps_per_second


def movement_for(
    action: str,
    value: float,
    speed: float,
    direction: str,
    steps_per_revolution: int,
    default_max_steps_per_second: float,
) -> Movement:
    """The movement of a ``rotate`` (value = revolutions, speed = RPM) or ``steps`` (value = steps,
    speed = steps per second) command."""
    if action == "rotate":
        steps = rotations_to_steps(value, steps_per_revolution)
        speed_steps = rpm_to_steps_per_second(speed, steps_per_revolution)
    elif action == "steps":
        steps = int(abs(value))
        speed_steps = speed
    else:
        raise InvalidMovement(f"Unsupported action: {action}")
    return Movement(
        steps=steps,
        speed_steps_per_second=resolve_speed(speed_steps, default_max_steps_per_second),
        forward=is_forward(direction),
    )
