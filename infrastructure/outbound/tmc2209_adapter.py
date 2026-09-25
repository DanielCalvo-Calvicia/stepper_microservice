import asyncio
import time
from application.ports.adapter_outbound_port import AdapterOutboundPort
from application.dtos.adapter_outbound_dtos import InitOutboundAdapterDto, MotorCommandDto, MotorStatusDto
from shared_logging import get_logger

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

logger = get_logger("infrastructure.outbound.tmc2209")

class TMC2209Adapter(AdapterOutboundPort):
    def __init__(self, config: InitOutboundAdapterDto):
        self.config = config
        self.stop_events: dict[str, asyncio.Event] = {}
        self.active_tasks: dict[str, asyncio.Task] = {}
        
        logger.info("TMC2209Adapter initializing...")
        if not GPIO_AVAILABLE:
            logger.error("RPi.GPIO is not available. Hardware operations will fail.")
            # We continue initialization so the process doesn't immediately crash if only instantiated conditionally.
            
        else:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            
            for stepper_id, pin_config in config.steppers.items():
                logger.info(
                    "Configuring TMC2209",
                    stepper_id=stepper_id,
                    step_pin=pin_config.step_pin,
                    dir_pin=pin_config.dir_pin,
                    en_pin=pin_config.en_pin,
                )
                
                # Setup pins
                GPIO.setup(pin_config.step_pin, GPIO.OUT, initial=GPIO.LOW)
                GPIO.setup(pin_config.dir_pin, GPIO.OUT, initial=GPIO.LOW)
                # Note: Most TMC2209 are active-low enable. High = disabled, Low = enabled.
                GPIO.setup(pin_config.en_pin, GPIO.OUT, initial=GPIO.HIGH)
                
                self.stop_events[stepper_id] = asyncio.Event()

    def _set_enable(self, stepper_id: str, enabled: bool):
        if not GPIO_AVAILABLE: return
        pin_config = self.config.steppers[stepper_id]
        # Active low: False means output LOW (enabled), True means output HIGH (disabled)
        level = GPIO.LOW if enabled else GPIO.HIGH
        GPIO.output(pin_config.en_pin, level)

    def _set_direction(self, stepper_id: str, forward: bool):
        if not GPIO_AVAILABLE: return
        pin_config = self.config.steppers[stepper_id]
        level = GPIO.HIGH if forward else GPIO.LOW
        GPIO.output(pin_config.dir_pin, level)

    def _run_sync_pulse_loop(
        self,
        stepper_id: str,
        steps: int,
        high_time_sec: float,
        low_time_sec: float,
        stop_event: asyncio.Event,
    ) -> tuple[int, bool]:
        if not GPIO_AVAILABLE:
            return 0, False

        pin_config = self.config.steppers[stepper_id]
        steps_completed = 0

        for _ in range(steps):
            if stop_event.is_set():
                logger.warning(
                    "TMC2209 stopped early",
                    stepper_id=stepper_id,
                    steps_completed=steps_completed,
                )
                return steps_completed, True

            GPIO.output(pin_config.step_pin, GPIO.HIGH)
            if high_time_sec > 0:
                time.sleep(high_time_sec)
            GPIO.output(pin_config.step_pin, GPIO.LOW)
            if low_time_sec > 0:
                time.sleep(low_time_sec)

            steps_completed += 1

        return steps_completed, False

    async def _execute_hardware_movement(self, request: MotorCommandDto) -> MotorStatusDto:
        if not GPIO_AVAILABLE:
            return MotorStatusDto(success=False, message="Hardware library missing.")
            
        stop_event = self.stop_events.get(request.stepper_id)
        if not stop_event:
            return MotorStatusDto(success=False, message=f"Invalid stepper: {request.stepper_id}")
            
        stop_event.clear()
        
        if request.speed_steps_per_sec <= 0:
            return MotorStatusDto(success=False, message="Speed must be greater than 0")

        period_sec = 1.0 / request.speed_steps_per_sec
        # Hardcode pulse width to something safe for TMC2209 (e.g. 1ms)
        high_time_sec = min(0.001, period_sec / 2.0)
        low_time_sec = max(period_sec - high_time_sec, 0.0)

        # Enable the driver
        self._set_enable(request.stepper_id, True)
        # Set direction
        self._set_direction(request.stepper_id, request.forward)

        logger.info(
            "TMC2209 starting movement",
            stepper_id=request.stepper_id,
            steps=request.steps,
            speed_steps_per_sec=request.speed_steps_per_sec,
        )

        try:
            loop = asyncio.get_running_loop()
            steps_completed, stopped_early = await loop.run_in_executor(
                None,
                self._run_sync_pulse_loop,
                request.stepper_id,
                request.steps,
                high_time_sec,
                low_time_sec,
                stop_event,
            )

            if stopped_early:
                return MotorStatusDto(success=True, message=f"Stopped early at {steps_completed}/{request.steps} steps.")
        finally:
            # We don't necessarily disable the driver here if holding torque is required, 
            # but standard practice is to disable after movement to save power/heat unless 
            # specifically requested. Let's disable for safety in this basic implementation.
            self._set_enable(request.stepper_id, False)

        logger.info("TMC2209 completed movement", stepper_id=request.stepper_id)
        return MotorStatusDto(success=True, message=f"Successfully completed {request.steps} steps.")

    async def execute_movement(self, request: MotorCommandDto) -> MotorStatusDto:
        task = asyncio.create_task(self._execute_hardware_movement(request))
        self.active_tasks[request.stepper_id] = task
        try:
            return await task
        except asyncio.CancelledError:
            return MotorStatusDto(success=False, message="Movement task cancelled.")
        finally:
            if self.active_tasks.get(request.stepper_id) == task:
                del self.active_tasks[request.stepper_id]

    async def emergency_stop(self, stepper_id: str) -> MotorStatusDto:
        stop_event = self.stop_events.get(stepper_id)
        if stop_event:
            stop_event.set()
            logger.info("Emergency stop sent to TMC2209", stepper_id=stepper_id)
            return MotorStatusDto(success=True, message="Stop signal dispatched.")
        return MotorStatusDto(success=False, message="Invalid stepper_id")

    async def cleanup(self) -> MotorStatusDto:
        logger.info("Cleaning up TMC2209 resources.")
        for stepper_id, event in self.stop_events.items():
            event.set()
            # Disable all drivers
            self._set_enable(stepper_id, False)
            
        await asyncio.sleep(0.1) # Yield to allow tasks to exit
        if GPIO_AVAILABLE:
            GPIO.cleanup()
        return MotorStatusDto(success=True, message="Hardware cleanup completed.")

    def is_available(self) -> bool:
        return GPIO_AVAILABLE
