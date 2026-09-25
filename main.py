import asyncio
import sys

from dotenv import find_dotenv, load_dotenv
from shared_logging import get_logger, init_logging

from composition_root.setup.setup import setup
from runtime.environment import resolve_runtime_environment

# Load .env first so LOG_LEVEL / SERVICE_NAME / TRACE_EXPORT_* apply to the very first log line.
load_dotenv(find_dotenv(".env"))
runtime_environment = resolve_runtime_environment()
init_logging("stepper", environment=runtime_environment.name)
logger = get_logger("main")

if __name__ == "__main__":
    try:
        logger.info(
            "Stepper microservice process entrypoint reached",
            environment=runtime_environment.name,
            source=runtime_environment.source,
        )
        asyncio.run(setup())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Exiting stepper microservice.")
        sys.exit(0)
    except Exception:
        logger.exception("Unhandled exception reached process entrypoint.")
        raise
