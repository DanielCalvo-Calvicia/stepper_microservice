from dataclasses import dataclass
import asyncio
from typing import AsyncIterator, Any

@dataclass(slots=True, frozen=True)
class InitInboundAdapterDto:
    """Configures the inbound HTTP/WebSocket network adapter."""
    allow_origins: tuple[str, ...] = ("*",)


@dataclass(slots=True, frozen=True)
class StepperBatchRequestDto:
    """Inbound client payload for a single batch command (e.g., rotate, steps, stop)."""
    stepper_id: str
    action: str  # 'rotate', 'steps', 'stop'
    value: float = 0.0  # degrees or number of steps
    speed: float = 0.0  # steps per second (or RPM mapped to steps per sec)
    direction: str = "forward"  # 'forward' or 'reverse'

@dataclass(slots=True, frozen=True)
class StepperBatchResponseDto:
    """Outcome of a batch command execution."""
    success: bool
    message: str


@dataclass(slots=True, frozen=True)
class StepperStreamRequestDto:
    """Inbound client payload delivering a stream of motor commands."""
    stepper_id: str
    command_stream: AsyncIterator[dict[str, Any]]
    setup_future: asyncio.Future[Any] | None = None

@dataclass(slots=True, frozen=True)
class StepperStreamResponseDto:
    """Outcome of starting/queuing the stream."""
    success: bool
    message: str
