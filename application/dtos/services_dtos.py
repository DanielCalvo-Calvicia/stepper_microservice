from dataclasses import dataclass
import asyncio
from typing import AsyncIterator, Any

@dataclass(slots=True, frozen=True)
class ServiceBatchRequestDto:
    stepper_id: str
    action: str  # 'rotate', 'steps', 'stop'
    value: float
    speed: float
    direction: str

@dataclass(slots=True, frozen=True)
class ServiceBatchResponseDto:
    success: bool
    message: str


@dataclass(slots=True, frozen=True)
class ServiceStreamRequestDto:
    stepper_id: str
    command_stream: AsyncIterator[dict[str, Any]]
    setup_future: asyncio.Future[Any] | None = None

@dataclass(slots=True, frozen=True)
class ServiceStreamResponseDto:
    success: bool
    message: str
