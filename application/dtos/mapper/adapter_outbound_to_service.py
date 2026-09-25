from application.dtos.adapter_outbound_dtos import MotorStatusDto
from application.dtos.services_dtos import ServiceBatchResponseDto
from shared_logging import get_logger

logger = get_logger("application.mapper.outbound_to_service")

def map_outbound_to_service_response(response: MotorStatusDto) -> ServiceBatchResponseDto:
    logger.debug("Mapping outbound response to service DTO")
    return ServiceBatchResponseDto(
        success=response.success,
        message=response.message
    )
