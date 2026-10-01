from typing import Any

from contracts.api.common.envelope import ApiEnvelope
from contracts.api.microservices.stepper.batch import StepperBatchResult
from fastapi import status
from fastapi.responses import JSONResponse
from shared_logging import get_logger

from infrastructure.inbound.http.http_error_mapper import map_error

logger = get_logger(__name__)

# The JSON shape of every non-stream answer is the project contract ``ApiEnvelope``; ``data`` is
# the endpoint's contract dataclass (``contracts.api.microservices``).


def success(
    action: str,
    message: str,
    data: Any = None,  # noqa: ANN401 - a contract dataclass or plain JSON
    *,
    code: int = status.HTTP_200_OK,
) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content=ApiEnvelope.success(action, message, data, status_code=code).to_dict(),
    )


def failure(action: str, message: str, error: Exception) -> JSONResponse:
    """The failure of a control route: its ``data`` is a ``StepperBatchResult`` like the success."""
    logger.error("Operation failed", action=action, error=error)
    code = map_error(error)
    return JSONResponse(
        status_code=code,
        content=ApiEnvelope.failure(
            action,
            f"{message}: {error}",
            code,
            StepperBatchResult(success=False, message=str(error)),
        ).to_dict(),
    )
