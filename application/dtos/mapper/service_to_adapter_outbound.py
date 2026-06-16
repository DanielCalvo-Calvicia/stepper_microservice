from application.dtos.services_dtos import ServiceBatchRequestDto
from application.dtos.adapter_outbound_dtos import MotorCommandDto
from runtime.logger import get_logger

logger = get_logger("application.mapper.service_to_outbound")

def map_service_to_outbound_motor_command(request: ServiceBatchRequestDto, actual_steps: int, steps_per_sec: float) -> MotorCommandDto:
    """
    Transforms the abstract business request into physical motor commands.
    Converts degrees to steps if needed, and normalizes direction.
    """
    logger.trace("Mapping service request to outbound motor command")
    return MotorCommandDto(
        stepper_id=request.stepper_id,
        action=request.action,
        steps=actual_steps,
        speed_steps_per_sec=steps_per_sec,
        forward=(request.direction.lower() == "forward" or request.direction.lower() == "clockwise")
    )
