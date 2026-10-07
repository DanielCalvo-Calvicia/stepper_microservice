import asyncio
import time
from collections.abc import Mapping
from typing import Any

from shared_logging import get_logger

from application.dtos.motor_command_outbound import MotorCommandOutboundDTO, MotorStatusOutboundDTO
from application.ports.outbound.motor_driver_port import MotorDriverPort
from infrastructure.config.stepper_config import StepperPins

try:
    import RPi.GPIO as _GPIO

    GPIO: Any = _GPIO

    GPIO_AVAILABLE = True
except ImportError:
    GPIO = None
    GPIO_AVAILABLE = False

logger = get_logger(__name__)


class TMC2209MotorDriver(MotorDriverPort):
    """Drives TMC2209 stepper drivers through the Raspberry Pi GPIO (BCM numbering)."""

    def __init__(self, steppers: Mapping[str, StepperPins]) -> None:
        self._steppers = steppers
        self._stop_events: dict[str, asyncio.Event] = {}

        logger.info("TMC2209MotorDriver initializing")
        if not GPIO_AVAILABLE:
            # Initialization continues so the process does not crash when this is only instantiated
            # conditionally; every movement then fails with a clear message.
            logger.error("RPi.GPIO is not available. Hardware operations will fail.")
            return

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        for stepper_id, pins in steppers.items():
            logger.info(
                "Configuring TMC2209",
                stepper_id=stepper_id,
                step_pin=pins.step_pin,
                dir_pin=pins.dir_pin,
                en_pin=pins.en_pin,
            )
            GPIO.setup(pins.step_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(pins.dir_pin, GPIO.OUT, initial=GPIO.LOW)
            # Most TMC2209 boards are active-low enable: HIGH = disabled, LOW = enabled.
            GPIO.setup(pins.en_pin, GPIO.OUT, initial=GPIO.HIGH)
            self._stop_events[stepper_id] = asyncio.Event()

    def _set_enable(self, stepper_id: str, enabled: bool) -> None:
        if not GPIO_AVAILABLE:
            return
        GPIO.output(self._steppers[stepper_id].en_pin, GPIO.LOW if enabled else GPIO.HIGH)

    def _set_direction(self, stepper_id: str, forward: bool) -> None:
        if not GPIO_AVAILABLE:
            return
        GPIO.output(self._steppers[stepper_id].dir_pin, GPIO.HIGH if forward else GPIO.LOW)

    def _run_sync_pulse_loop(
        self,
        stepper_id: str,
        steps: int,
        high_time_seconds: float,
        low_time_seconds: float,
        stop_event: asyncio.Event,
    ) -> tuple[int, bool]:
        if not GPIO_AVAILABLE:
            return 0, False

        step_pin = self._steppers[stepper_id].step_pin
        steps_completed = 0
        for _ in range(steps):
            if stop_event.is_set():
                logger.warning(
                    "TMC2209 stopped early", stepper_id=stepper_id, steps_completed=steps_completed
                )
                return steps_completed, True
            GPIO.output(step_pin, GPIO.HIGH)
            if high_time_seconds > 0:
                time.sleep(high_time_seconds)
            GPIO.output(step_pin, GPIO.LOW)
            if low_time_seconds > 0:
                time.sleep(low_time_seconds)
            steps_completed += 1
        return steps_completed, False

    async def execute_movement(self, command: MotorCommandOutboundDTO) -> MotorStatusOutboundDTO:
        if not GPIO_AVAILABLE:
            return MotorStatusOutboundDTO(False, "Hardware library missing.")
        stop_event = self._stop_events.get(command.stepper_id)
        if stop_event is None:
            return MotorStatusOutboundDTO(False, f"Invalid stepper: {command.stepper_id}")
        if command.speed_steps_per_second <= 0:
            return MotorStatusOutboundDTO(False, "Speed must be greater than 0")

        stop_event.clear()
        period_seconds = 1.0 / command.speed_steps_per_second
        # A fixed 1 ms pulse width is safe for a TMC2209.
        high_time_seconds = min(0.001, period_seconds / 2.0)
        low_time_seconds = max(period_seconds - high_time_seconds, 0.0)

        self._set_enable(command.stepper_id, True)
        self._set_direction(command.stepper_id, command.forward)
        logger.info(
            "TMC2209 starting movement",
            stepper_id=command.stepper_id,
            steps=command.steps,
            speed_steps_per_second=command.speed_steps_per_second,
        )
        try:
            steps_completed, stopped_early = await asyncio.get_running_loop().run_in_executor(
                None,
                self._run_sync_pulse_loop,
                command.stepper_id,
                command.steps,
                high_time_seconds,
                low_time_seconds,
                stop_event,
            )
            if stopped_early:
                return MotorStatusOutboundDTO(
                    True, f"Stopped early at {steps_completed}/{command.steps} steps."
                )
        finally:
            # Disable the driver after a movement to save power and heat.
            self._set_enable(command.stepper_id, False)
        logger.info("TMC2209 completed movement", stepper_id=command.stepper_id)
        return MotorStatusOutboundDTO(True, f"Successfully completed {command.steps} steps.")

    async def emergency_stop(self, stepper_id: str) -> MotorStatusOutboundDTO:
        stop_event = self._stop_events.get(stepper_id)
        if stop_event is None:
            return MotorStatusOutboundDTO(False, "Invalid stepper_id")
        stop_event.set()
        logger.info("Emergency stop sent to TMC2209", stepper_id=stepper_id)
        return MotorStatusOutboundDTO(True, "Stop signal dispatched.")

    async def cleanup(self) -> MotorStatusOutboundDTO:
        logger.info("Cleaning up TMC2209 resources")
        for stepper_id, event in self._stop_events.items():
            event.set()
            self._set_enable(stepper_id, False)
        await asyncio.sleep(0.1)  # let a running movement exit
        if GPIO_AVAILABLE:
            GPIO.cleanup()
        return MotorStatusOutboundDTO(True, "Hardware cleanup completed.")

    def is_available(self) -> bool:
        return GPIO_AVAILABLE
