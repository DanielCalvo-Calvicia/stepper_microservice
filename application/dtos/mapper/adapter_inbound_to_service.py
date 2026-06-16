from application.dtos.adapter_inbound_dtos import StepperBatchRequestDto, StepperStreamRequestDto
from application.dtos.services_dtos import ServiceBatchRequestDto, ServiceStreamRequestDto
from runtime.logger import get_logger

logger = get_logger("application.mapper.inbound_to_service")

def map_inbound_to_service_batch_request(request: StepperBatchRequestDto) -> ServiceBatchRequestDto:
    logger.trace("Mapping inbound batch request to service DTO")
    return ServiceBatchRequestDto(
        stepper_id=request.stepper_id,
        action=request.action,
        value=request.value,
        speed=request.speed,
        direction=request.direction
    )

def map_inbound_to_service_stream_request(request: StepperStreamRequestDto) -> ServiceStreamRequestDto:
    logger.trace("Mapping inbound stream request to service DTO")
    return ServiceStreamRequestDto(
        stepper_id=request.stepper_id,
        command_stream=request.command_stream,
        setup_future=request.setup_future
    )
