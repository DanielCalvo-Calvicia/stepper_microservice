from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from shared_logging import get_logger, init_logging

from composition_root.containers.http_container import HttpContainer, new_http_container
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stepper_config import StepperConfig

logger = get_logger(__name__)

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


async def run_http() -> None:
    # Load .env first so LOG_LEVEL / SERVICE_NAME / TRACE_EXPORT_* apply to the very first log line.
    load_dotenv(dotenv_path=_ENV_FILE)
    server_cfg = ServerConfig.from_env()
    stepper_cfg = StepperConfig.from_env()
    init_logging("stepper")

    container = new_http_container(server_cfg, stepper_cfg)
    server = uvicorn.Server(
        uvicorn.Config(
            container.app,
            host=server_cfg.host,
            port=server_cfg.port,
            log_config=None,
            timeout_keep_alive=60,
        )
    )
    logger.info(
        "Starting server",
        service_name=server_cfg.service_name,
        host=server_cfg.host,
        port=server_cfg.port,
        steppers=list(stepper_cfg.steppers),
    )
    try:
        await server.serve()  # returns after SIGINT/SIGTERM; the app lifespan releases the hardware
    finally:
        await _cleanup(container)


async def _cleanup(container: HttpContainer) -> None:
    logger.info("Server stopped; making sure the motors are released")
    try:
        await container.stepper.stop_and_cleanup()
    except Exception:
        logger.exception("Failed to stop the motors during cleanup")
    logger.info("Cleanup finished")
