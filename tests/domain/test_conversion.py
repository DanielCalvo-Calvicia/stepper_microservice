import pytest

from domain.errors import InvalidMovement
from domain.operations import conversion
from domain.value_objects.movement import Movement


def test_rotations_become_steps_and_the_sign_is_dropped():
    assert conversion.rotations_to_steps(1.0, 400) == 400
    assert conversion.rotations_to_steps(-0.25, 400) == 100


def test_rpm_becomes_steps_per_second():
    assert conversion.rpm_to_steps_per_second(60, 400) == 400.0
    assert conversion.rpm_to_steps_per_second(-60, 400) == -400.0


def test_zero_speed_is_the_default_limit_and_negative_speed_is_rejected():
    assert conversion.resolve_speed(0.0, 1000.0) == 1000.0
    assert conversion.resolve_speed(250.0, 1000.0) == 250.0
    with pytest.raises(InvalidMovement):
        conversion.resolve_speed(-1.0, 1000.0)


@pytest.mark.parametrize("direction", ["forward", "FORWARD", "clockwise"])
def test_forward_names(direction):
    assert conversion.is_forward(direction) is True


@pytest.mark.parametrize("direction", ["reverse", "counterclockwise"])
def test_reverse_names(direction):
    assert conversion.is_forward(direction) is False


def test_unknown_direction_is_rejected():
    with pytest.raises(InvalidMovement):
        conversion.is_forward("sideways")


def test_movement_for_rotate_and_steps():
    rotate = conversion.movement_for("rotate", 0.5, 30, "reverse", 400, 1000.0)
    assert rotate == Movement(steps=200, speed_steps_per_second=200.0, forward=False)
    steps = conversion.movement_for("steps", -50, 0, "forward", 400, 1000.0)
    assert steps == Movement(steps=50, speed_steps_per_second=1000.0, forward=True)


def test_movement_for_rejects_other_actions():
    with pytest.raises(InvalidMovement):
        conversion.movement_for("stop", 0, 0, "forward", 400, 1000.0)


def test_movement_invariants():
    with pytest.raises(InvalidMovement):
        Movement(steps=-1, speed_steps_per_second=1.0, forward=True)
    with pytest.raises(InvalidMovement):
        Movement(steps=1, speed_steps_per_second=0.0, forward=True)
