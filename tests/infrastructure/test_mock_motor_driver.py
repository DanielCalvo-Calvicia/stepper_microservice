import asyncio

import pytest

from application.dtos.motor_command_outbound import MotorCommandOutboundDTO
from infrastructure.config.stepper_config import StepperPins
from infrastructure.outbound.mock_motor.mock_motor_driver import MockMotorDriver

PINS = {"stepper_1": StepperPins(17, 27, 5)}


@pytest.mark.asyncio
async def test_a_movement_completes():
    driver = MockMotorDriver(PINS)
    status = await driver.execute_movement(MotorCommandOutboundDTO("stepper_1", 5, 10000.0, True))
    assert status.success and "5 steps" in status.message


@pytest.mark.asyncio
async def test_an_unknown_stepper_or_a_zero_speed_fails():
    driver = MockMotorDriver(PINS)
    assert not (await driver.execute_movement(MotorCommandOutboundDTO("nope", 5, 100.0, True))).success
    assert not (await driver.execute_movement(MotorCommandOutboundDTO("stepper_1", 5, 0.0, True))).success
    assert not (await driver.emergency_stop("nope")).success


@pytest.mark.asyncio
async def test_an_emergency_stop_ends_a_movement_early():
    driver = MockMotorDriver(PINS)
    move = asyncio.create_task(
        driver.execute_movement(MotorCommandOutboundDTO("stepper_1", 100000, 1000.0, True))
    )
    await asyncio.sleep(0.05)
    assert (await driver.emergency_stop("stepper_1")).success
    status = await move
    assert status.success and "Stopped early" in status.message


@pytest.mark.asyncio
async def test_cleanup_and_availability():
    driver = MockMotorDriver(PINS)
    assert driver.is_available() is True
    assert (await driver.cleanup()).success
