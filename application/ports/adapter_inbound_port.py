from abc import ABC, abstractmethod
from typing import Any
from application.dtos.adapter_inbound_dtos import StepperBatchRequestDto, StepperBatchResponseDto, StepperStreamRequestDto, StepperStreamResponseDto

class AdapterInboundPort(ABC):
    @abstractmethod
    async def process_batch(self, request: StepperBatchRequestDto) -> StepperBatchResponseDto:
        """Coordinate and validate a batch motor command."""
        pass

    @abstractmethod
    async def process_stream(self, request: StepperStreamRequestDto) -> StepperStreamResponseDto:
        """Coordinate and validate an incoming stream of motor commands."""
        pass

    @property
    @abstractmethod
    def get_app(self) -> Any:
        """Return the underlying framework application instance (e.g., FastAPI app)."""
        pass
