from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MoveCommandInboundDTO:
    """One motor command, from a batch route or from one event of a command stream."""

    stepper_id: str
    action: str  # 'rotate', 'steps' or 'stop'
    value: float = 0.0  # rotate -> full revolutions; steps -> number of steps
    speed: float = 0.0  # rotate -> RPM; steps -> steps per second; 0 = the default speed limit
    direction: str = "forward"  # 'forward' or 'reverse'
