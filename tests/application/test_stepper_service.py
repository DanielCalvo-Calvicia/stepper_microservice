import asyncio

import pytest

from application.dtos.motor_command_outbound import MotorCommandOutboundDTO, MotorStatusOutboundDTO
from application.dtos.move_command_inbound import MoveCommandInboundDTO
from application.errors import MotorFailed, StepperBusy, UnknownStepper
from application.ports.outbound.motor_driver_port import MotorDriverPort
from application.services.stepper_service import StepperService
from domain.errors import InvalidMovement


class FakeDriver(MotorDriverPort):
    def __init__(self, ok=True, available=True, hold=None):
        self.moves: list[MotorCommandOutboundDTO] = []
        self.stops: list[str] = []
        self.cleaned = False
        self._ok, self._available, self._hold = ok, available, hold

    async def execute_movement(self, command):
        self.moves.append(command)
        if self._hold is not None:
            await self._hold.wait()
        return MotorStatusOutboundDTO(self._ok, "moved" if self._ok else "driver exploded")

    async def emergency_stop(self, stepper_id):
        self.stops.append(stepper_id)
        return MotorStatusOutboundDTO(True, "Stop signal dispatched.")

    async def cleanup(self):
        self.cleaned = True
        return MotorStatusOutboundDTO(True, "done")

    def is_available(self):
        return self._available


def _service(driver):
    return StepperService(driver, ["stepper_1", "stepper_2"], 1000.0, 400)


async def _commands(*commands):
    for command in commands:
        yield command


@pytest.mark.asyncio
async def test_rotate_is_converted_to_steps_and_speed():
    driver = FakeDriver()
    result = await _service(driver).execute(
        MoveCommandInboundDTO("stepper_1", "rotate", 0.5, 30, "reverse")
    )
    assert result.success and result.action == "rotate"
    assert driver.moves == [MotorCommandOutboundDTO("stepper_1", 200, 200.0, False)]


@pytest.mark.asyncio
async def test_steps_use_the_default_speed_when_none_is_given():
    driver = FakeDriver()
    await _service(driver).execute(MoveCommandInboundDTO("stepper_2", "steps", 10))
    assert driver.moves == [MotorCommandOutboundDTO("stepper_2", 10, 1000.0, True)]


@pytest.mark.asyncio
async def test_unknown_stepper_is_rejected_before_the_driver_is_touched():
    driver = FakeDriver()
    with pytest.raises(UnknownStepper, match="no_such"):
        await _service(driver).execute(MoveCommandInboundDTO("no_such", "steps", 10))
    assert driver.moves == []


@pytest.mark.asyncio
async def test_invalid_commands_are_rejected():
    service = _service(FakeDriver())
    with pytest.raises(InvalidMovement):
        await service.execute(MoveCommandInboundDTO("stepper_1", "fly"))
    with pytest.raises(InvalidMovement):
        await service.execute(MoveCommandInboundDTO("stepper_1", "steps", 10, -5))
    with pytest.raises(InvalidMovement):
        await service.execute(MoveCommandInboundDTO("stepper_1", "steps", 10, 5, "sideways"))


@pytest.mark.asyncio
async def test_a_driver_failure_is_a_motor_failed_error():
    with pytest.raises(MotorFailed, match="exploded"):
        await _service(FakeDriver(ok=False)).execute(MoveCommandInboundDTO("stepper_1", "steps", 10))


@pytest.mark.asyncio
async def test_a_busy_motor_rejects_a_second_movement_but_still_accepts_a_stop():
    hold = asyncio.Event()
    driver = FakeDriver(hold=hold)
    service = _service(driver)
    first = asyncio.create_task(service.execute(MoveCommandInboundDTO("stepper_1", "steps", 10)))
    await asyncio.sleep(0)
    with pytest.raises(StepperBusy):
        await service.execute(MoveCommandInboundDTO("stepper_1", "steps", 10))
    stop = await service.execute(MoveCommandInboundDTO("stepper_1", "stop"))
    assert stop.success and driver.stops == ["stepper_1"]
    hold.set()
    assert (await first).success


@pytest.mark.asyncio
async def test_a_stream_runs_commands_in_order_and_reports_each_result():
    driver = FakeDriver()
    results = [
        r
        async for r in _service(driver).run_commands(
            "stepper_1",
            _commands(
                MoveCommandInboundDTO("stepper_1", "steps", 5),
                MoveCommandInboundDTO("stepper_1", "steps", 7, 0, "reverse"),
            ),
        )
    ]
    assert [r.success for r in results] == [True, True]
    assert [(m.steps, m.forward) for m in driver.moves] == [(5, True), (7, False)]


@pytest.mark.asyncio
async def test_a_failed_command_ends_the_stream():
    driver = FakeDriver()
    results = [
        r
        async for r in _service(driver).run_commands(
            "stepper_1",
            _commands(
                MoveCommandInboundDTO("stepper_1", "steps", 5),
                MoveCommandInboundDTO("stepper_1", "fly"),
                MoveCommandInboundDTO("stepper_1", "steps", 9),
            ),
        )
    ]
    assert [r.success for r in results] == [True, False]
    assert "fly" in results[1].message
    assert len(driver.moves) == 1  # the command after the failure never ran


@pytest.mark.asyncio
async def test_a_stream_for_an_unknown_stepper_fails_at_once():
    with pytest.raises(UnknownStepper):
        async for _ in _service(FakeDriver()).run_commands("nope", _commands()):
            pass


@pytest.mark.asyncio
async def test_cleanup_and_availability_go_to_the_driver():
    driver = FakeDriver(available=False)
    service = _service(driver)
    await service.stop_and_cleanup()
    assert driver.cleaned and service.is_available() is False
