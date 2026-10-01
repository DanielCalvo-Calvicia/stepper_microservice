from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CommandResultOutboundDTO:
    """The outcome of one command. A failing command raises; a stream reports it as a result."""

    action: str
    success: bool
    message: str
