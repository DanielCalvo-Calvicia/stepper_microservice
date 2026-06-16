from application.dtos.services_dtos import ServiceBatchResponseDto, ServiceStreamResponseDto
from application.dtos.adapter_inbound_dtos import StepperBatchResponseDto, StepperStreamResponseDto
from runtime.logger import get_logger

logger = get_logger("application.mapper.service_to_inbound")

def map_service_to_inbound_batch_response(response: ServiceBatchResponseDto) -> StepperBatchResponseDto:
    logger.trace("Mapping service batch response to inbound DTO")
    return StepperBatchResponseDto(
        success=response.success,
        message=response.message
    )

def map_service_to_inbound_stream_response(response: ServiceStreamResponseDto) -> StepperStreamResponseDto:
    logger.trace("Mapping service stream response to inbound DTO")
    return StepperStreamResponseDto(
        success=response.success,
        message=response.message
    )
