from abc import ABC, abstractmethod
from application.dtos.adapter_outbound_dtos import MotorCommandDto, MotorStatusDto

class AdapterOutboundPort(ABC):
    @abstractmethod
    async def execute_movement(self, request: MotorCommandDto) -> MotorStatusDto:
        """Command the physical hardware to move the stepper."""
        pass

    @abstractmethod
    async def emergency_stop(self, stepper_id: str) -> MotorStatusDto:
        """Immediately halt movement for a specific stepper."""
        pass

    @abstractmethod
    async def cleanup(self) -> MotorStatusDto:
        """Release hardware resources gracefully."""
        pass
