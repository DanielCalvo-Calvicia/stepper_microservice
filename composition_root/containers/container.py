from dataclasses import dataclass
from composition_root.dependencies.stepper_dependency import StepperDependency, generate_stepper_dependency
from runtime.logger import get_logger

logger = get_logger("container")

@dataclass(slots=True, frozen=True)
class Container:
    stepper_dependency: StepperDependency

def BuildContainer(name: str) -> Container:
    """Instantiate and compile all system dependency trees."""
    logger.info("Building container: %s", name)
    stepper_dep = generate_stepper_dependency()
    container = Container(stepper_dependency=stepper_dep)
    logger.info("Container built: %s", name)
    return container
