from dataclasses import dataclass

from fastapi import FastAPI

from application.ports.inbound.stepper_control_port import StepperControlPort
from composition_root.dependencies import stepper_dependencies as deps
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stepper_config import StepperConfig


@dataclass(slots=True, frozen=True)
class HttpContainer:
    app: FastAPI
    stepper: StepperControlPort  # kept so main_flow can release the hardware on shutdown


def new_http_container(server_cfg: ServerConfig, stepper_cfg: StepperConfig) -> HttpContainer:
    driver = deps.new_motor_driver(stepper_cfg)
    service = deps.new_stepper_service(driver, stepper_cfg, server_cfg.service_name)
    app = deps.new_http_app(service, server_cfg.service_name, server_cfg.allowed_origins)
    return HttpContainer(app=app, stepper=service)
