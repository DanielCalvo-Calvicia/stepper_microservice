import pytest
from fastapi import status

from application.errors import MotorFailed, StepperBusy, UnknownStepper
from domain.errors import InvalidMovement
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stepper_config import StepperConfig
from infrastructure.inbound.http.http_error_mapper import map_error
from infrastructure.inbound.http.ndjson_command_decoder import NdjsonInputError


def test_server_defaults():
    cfg = ServerConfig.from_env({})
    assert (cfg.service_name, cfg.host, cfg.port, cfg.allowed_origins) == (
        "Stepper Microservice",
        "127.0.0.1",
        8005,
        ("*",),
    )


def test_server_settings_come_from_the_environment():
    cfg = ServerConfig.from_env(
        {"SERVICE_NAME": "Arms", "SERVICE_HOST": "0.0.0.0", "SERVICE_PORT": "9005", "ALLOWED_ORIGINS": "a, b"}
    )
    assert (cfg.service_name, cfg.host, cfg.port, cfg.allowed_origins) == ("Arms", "0.0.0.0", 9005, ("a", "b"))


def test_stepper_defaults():
    cfg = StepperConfig.from_env({})
    assert list(cfg.steppers) == ["stepper_1"]
    assert (cfg.steppers["stepper_1"].step_pin, cfg.steppers["stepper_1"].dir_pin, cfg.steppers["stepper_1"].en_pin) == (17, 27, 5)
    assert cfg.default_speed_limit == 1000.0
    assert cfg.steps_per_revolution == 400
    assert cfg.mock_hardware is False


def test_stepper_settings_come_from_the_environment():
    cfg = StepperConfig.from_env(
        {
            "STEPPER_CONFIGS": '{"left": {"step": 1, "dir": 2, "en": 3}}',
            "DEFAULT_SPEED_LIMIT": "250",
            "STEPS_PER_REVOLUTION": "1600",
            "MOCK_HARDWARE": "1",
        }
    )
    assert list(cfg.steppers) == ["left"] and cfg.steppers["left"].dir_pin == 2
    assert (cfg.default_speed_limit, cfg.steps_per_revolution, cfg.mock_hardware) == (250.0, 1600, True)


def test_invalid_steps_per_revolution_is_rejected():
    with pytest.raises(ValueError):
        StepperConfig.from_env({"STEPS_PER_REVOLUTION": "0"})


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (UnknownStepper("x"), status.HTTP_404_NOT_FOUND),
        (StepperBusy("x"), status.HTTP_409_CONFLICT),
        (InvalidMovement("x"), status.HTTP_422_UNPROCESSABLE_CONTENT),
        (NdjsonInputError("x"), status.HTTP_422_UNPROCESSABLE_CONTENT),
        (MotorFailed("x"), status.HTTP_502_BAD_GATEWAY),
        (RuntimeError("x"), status.HTTP_500_INTERNAL_SERVER_ERROR),
    ],
)
def test_errors_map_to_natural_statuses(error, code):
    assert map_error(error) == code
