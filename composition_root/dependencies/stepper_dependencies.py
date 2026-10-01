from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from shared_logging import TracingMiddleware, get_logger

from application.ports.inbound.stepper_control_port import StepperControlPort
from application.ports.outbound.motor_driver_port import MotorDriverPort
from application.services.stepper_service import StepperService
from infrastructure.config.stepper_config import StepperConfig
from infrastructure.inbound.http.http_handler import StepperHandler
from infrastructure.outbound.mock_motor.mock_motor_driver import MockMotorDriver
from infrastructure.outbound.tmc2209.tmc2209_motor_driver import GPIO_AVAILABLE, TMC2209MotorDriver

logger = get_logger(__name__)


def new_motor_driver(cfg: StepperConfig) -> MotorDriverPort:
    """The real TMC2209 driver on a Raspberry Pi, the mock anywhere else or when MOCK_HARDWARE=1."""
    if cfg.mock_hardware or not GPIO_AVAILABLE:
        logger.info("Instantiating the mock motor driver")
        return MockMotorDriver(cfg.steppers)
    logger.info("Instantiating the TMC2209 motor driver")
    return TMC2209MotorDriver(cfg.steppers)


def new_stepper_service(
    driver: MotorDriverPort, cfg: StepperConfig, name: str
) -> StepperControlPort:
    return StepperService(
        driver=driver,
        stepper_ids=tuple(cfg.steppers),
        default_max_speed=cfg.default_speed_limit,
        steps_per_revolution=cfg.steps_per_revolution,
        name=name,
    )


def new_http_app(port: StepperControlPort, name: str, allowed_origins: tuple[str, ...]) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        logger.info("Shutting down: stopping the motors and releasing the hardware")
        await port.stop_and_cleanup()

    app = FastAPI(
        title=name,
        description=f"HTTP adapter exposing {name}",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception in HTTP handler", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "An internal error occurred"},
        )

    allow_all = allowed_origins == ("*",)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(StepperHandler(port).router)
    app.add_middleware(TracingMiddleware)  # added last so it is outermost
    return app
