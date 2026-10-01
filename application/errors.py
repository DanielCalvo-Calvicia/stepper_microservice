class ApplicationError(Exception):
    """Base class for failures of a use case that are not business-rule violations."""


class UnknownStepper(ApplicationError, ValueError):
    """The ``stepper_id`` is not one of the configured motors.

    Also a ValueError so callers written against the previous behaviour keep working.
    """


class StepperBusy(ApplicationError, RuntimeError):
    """The motor is already executing a movement; commands on one motor never overlap."""


class MotorFailed(ApplicationError, RuntimeError):
    """The motor driver could not carry out the command (driver missing, hardware error)."""
