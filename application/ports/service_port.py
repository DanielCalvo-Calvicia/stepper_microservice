from abc import ABC, abstractmethod
from application.dtos.services_dtos import ServiceBatchRequestDto, ServiceBatchResponseDto, ServiceStreamRequestDto, ServiceStreamResponseDto

class StepperServicePort(ABC):
    @abstractmethod
    async def execute_batch(self, request: ServiceBatchRequestDto) -> ServiceBatchResponseDto:
        """Validate and route batch command to the outbound hardware port."""
        pass

    @abstractmethod
    async def execute_stream(self, request: ServiceStreamRequestDto) -> ServiceStreamResponseDto:
        """Validate and route stream commands to the outbound hardware port."""
        pass

    @abstractmethod
    async def stop_and_cleanup(self) -> ServiceBatchResponseDto:
        """Coordinate graceful teardown and release of device resources."""
        pass
