"""Domain errors.

They also inherit from the matching builtin exception so that callers written
against the pre-refactor behaviour (``ValueError``) keep working.
"""


class DomainError(Exception):
    """Base class for every business-rule violation raised by the domain."""


class InvalidMovement(DomainError, ValueError):
    """The requested movement violates an invariant (unknown action, direction or speed)."""
