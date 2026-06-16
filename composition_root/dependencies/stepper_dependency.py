import os
import json
from dataclasses import dataclass
from fastapi import FastAPI
from contextlib import asynccontextmanager

from application.services.service import StepperService
from application.dtos.adapter_outbound_dtos import InitOutboundAdapterDto, StepperConfigDto
from application.dtos.adapter_inbound_dtos import InitInboundAdapterDto
from infrastructure.outbound.mock_adapter import MockStepperAdapter
from infrastructure.outbound.tmc2209_adapter import TMC2209Adapter, GPIO_AVAILABLE
from infrastructure.inbound.http.fastapi_adapter import FastApiAdapter
from runtime.logger import get_logger

logger = get_logger("composition_root")

@dataclass(slots=True, frozen=True)
class StepperDependency:
    adapter_outbound: MockStepperAdapter | TMC2209Adapter
    service: StepperService
    adapter_inbound: FastApiAdapter

def generate_stepper_dependency() -> StepperDependency:
    logger.info("Generating stepper dependency graph.")

    # 1. Parse and compile Outbound configurations
    stepper_configs_json = os.getenv("STEPPER_CONFIGS", '{"stepper_1": {"step": 17, "dir": 27, "en": 5}}')
    try:
        parsed_configs = json.loads(stepper_configs_json)
        steppers_map = {
            k: StepperConfigDto(step_pin=v["step"], dir_pin=v["dir"], en_pin=v["en"])
            for k, v in parsed_configs.items()
        }
    except Exception as e:
        logger.error("Failed to parse STEPPER_CONFIGS from .env: %s", e)
        raise e

    default_speed = float(os.getenv("DEFAULT_SPEED_LIMIT", "1000.0"))
    outbound_config = InitOutboundAdapterDto(steppers=steppers_map, default_max_speed=default_speed)

    # Instantiate outbound adapter
    mock_hardware = os.getenv("MOCK_HARDWARE", "0") == "1"
    if mock_hardware or not GPIO_AVAILABLE:
        logger.info("Instantiating Mock outbound adapter.")
        adapter_outbound = MockStepperAdapter(config=outbound_config)
    else:
        logger.info("Instantiating TMC2209 outbound adapter.")
        adapter_outbound = TMC2209Adapter(config=outbound_config)

    # 2. Build core domain service
    logger.info("Instantiating stepper application service.")
    service = StepperService(outbound_port=adapter_outbound, steppers_config=parsed_configs, default_max_speed=default_speed)

    # 3. Handle FastAPI App configuration and Lifespan
    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        logger.info("FastAPI service lifecycle bootstrap sequence initiated.")
        yield
        logger.info("FastAPI service lifecycle shutdown sequence initiated. Running cleanups.")
        await service.stop_and_cleanup()
        logger.info("FastAPI service lifecycle shutdown cleanup finished.")

    logger.info("Creating FastAPI application instance.")
    app = FastAPI(
        title="Stepper Microservice",
        description="Low-latency raw stepper motor controller microservice",
        version="1.0.0",
        lifespan=app_lifespan
    )

    # 4. Instantiate inbound network adapter
    origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
    origins = tuple(o.strip() for o in origins_raw.split(",") if o.strip())
    
    inbound_config = InitInboundAdapterDto(allow_origins=origins)
    logger.info("Instantiating inbound FastAPI adapter.")
    adapter_inbound = FastApiAdapter(service_port=service, app=app, config=inbound_config)

    return StepperDependency(
        adapter_outbound=adapter_outbound,
        service=service,
        adapter_inbound=adapter_inbound
    )
