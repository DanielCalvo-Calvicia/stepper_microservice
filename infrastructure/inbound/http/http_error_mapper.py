from fastapi import status

from application.errors import MotorFailed, StepperBusy, UnknownStepper
from domain.errors import InvalidMovement
from infrastructure.inbound.http.ndjson_command_decoder import NdjsonInputError


def map_error(error: Exception) -> int:
    """Translate an application/domain error into an HTTP status code.

    404  unknown stepper_id
    409  the motor is busy with another movement
    422  the command is invalid (unknown action or direction, negative speed, bad stream)
    502  the motor driver failed
    500  anything else
    """
    if isinstance(error, UnknownStepper):
        return status.HTTP_404_NOT_FOUND
    if isinstance(error, StepperBusy):
        return status.HTTP_409_CONFLICT
    if isinstance(error, (InvalidMovement, NdjsonInputError)):
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    if isinstance(error, MotorFailed):
        return status.HTTP_502_BAD_GATEWAY
    return status.HTTP_500_INTERNAL_SERVER_ERROR
