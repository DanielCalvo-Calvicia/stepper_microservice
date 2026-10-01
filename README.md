# Stepper Microservice

HTTP service that drives the robot's stepper motors (two independent arms, `stepper_1` and `stepper_2` in `.env.example`) through TMC2209 drivers on a Raspberry Pi (`RPi.GPIO`), or a mock driver anywhere else. **Only Brain is meant to call it** (from the ai-agent's movement decisions); Brain calls the batch `/control/...` routes. It follows the same layered layout as microphone, stt, tts and speaker. Documentation reviewed against the code on 2026-10-01.

**Safety:** real motors move when a command reaches a Raspberry Pi with `MOCK_HARDWARE` not `1`. Never test those routes against real hardware without the owner present; use `MOCK_HARDWARE=1`.

## Run

```powershell
$env:MOCK_HARDWARE = "1"                       # no GPIO needed
windows\Scripts\python.exe main.py
```

Install with `pip install -r requirements.windows.txt` (or `requirements.linux.txt` on the Pi, which keeps mostly exact pins and adds `RPi.GPIO`; the Windows file uses lower bounds because the old pins have no Python 3.14 wheels). Real hardware only works on a Raspberry Pi: where `RPi.GPIO` cannot be imported the service falls back to the mock driver by itself. A `.env` next to `main.py` is loaded.

## Configuration

| Variable | Default (code) | In `.env.example` | Purpose |
|---|---|---|---|
| `SERVICE_NAME` | `Stepper Microservice` | same | API title / log name |
| `SERVICE_HOST` | `127.0.0.1` | same | Bind address; set e.g. `0.0.0.0` when Brain runs on another machine |
| `SERVICE_PORT` | `8005` | same | Bind port |
| `LOG_LEVEL` | `INFO` | same | Read by the shared logging module |
| `ALLOWED_ORIGINS` | `*` | same | Comma-separated CORS origins |
| `STEPPER_CONFIGS` | `{"stepper_1": {"step": 17, "dir": 27, "en": 5}}` | `stepper_1` (17/27/5) and `stepper_2` (23/24/25) | JSON: stepper id -> BCM pins `step`, `dir`, `en`. Invalid JSON stops startup |
| `DEFAULT_SPEED_LIMIT` | `1000.0` | same | Max speed in steps/s, applied when a command gives none |
| `STEPS_PER_REVOLUTION` | `400` | same | Step pulses per shaft revolution (full steps x microsteps); converts `rotations` to steps and `rpm` to steps/s. Must be > 0 |
| `MOCK_HARDWARE` | `0` | same | `1` forces the mock driver (anything else, including `true`, does not) |

`LOG_FORMAT`, `LOG_OUTPUT`, `ENVIRONMENT` and `TRACE_EXPORT_*` are also read by the shared logging package ([`shared-logging/docs/logging.md`](../shared-logging/docs/logging.md)). The local `.env` is tracked by git and was deliberately not committed.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `HealthCheckResponse{healthy}` |
| GET | `/available` | `AvailabilityResponse{is_available, reason}`: whether the motor driver (mock or TMC2209) initialized; moves nothing |
| POST | `/control/{stepper_id}/rotate?rotations=&rpm=&direction=` | Rotate by full revolutions (`rotations` required; `rpm` default 0 = use the speed limit; `direction` `forward`/`reverse`, default `forward`) |
| POST | `/control/{stepper_id}/steps?value=&speed=&direction=` | Move a number of steps (`value` required; `speed` in steps/s, default 0 = speed limit) |
| POST | `/control/{stepper_id}/stop` | Emergency stop (bypasses the busy lock) |
| POST | `/process/stream/{stepper_id}/set` | A live command stream, see below |

Control parameters are query parameters, not a JSON body. Answers use the envelope `action / status / status_code / message / timestamp / data` (`contracts.api.common.envelope.ApiEnvelope`); `data` is `StepperBatchResult{success, message}`, also on failures. Failures map to HTTP status codes in `infrastructure/inbound/http/http_error_mapper.py`: `404` unknown stepper, `409` the motor is busy (commands on one motor never overlap; a second one is rejected, not queued), `422` invalid command (unknown action or direction, negative speed), `502` the motor driver failed, `500` anything else. Brain treats any non-200 as a failed move. There is no authentication.

### Command stream

`POST /process/stream/{stepper_id}/set` takes `Content-Type: application/x-ndjson` events of `contracts.stream` (`STEPPER_INBOUND`): `stream_started` (`stepper_id`, which must match the URL), then one `partial` per command (`action` = `rotate` with `rotations` and `rpm`, `steps` with `steps` and `speed`, or `stop`; plus `direction`), then `completed`. Commands run in order as they arrive. The response (`application/x-ndjson`, `STEPPER_OUTBOUND`) is `stream_started`, one `partial` result per command (`action`, `success`, `message`) and `completed`. A command that fails is reported as a result with `success: false` and **ends the stream** (the rest is ignored: going on would leave the arm somewhere the sequence did not intend). A contract violation or a disconnect stops the motor and ends with an `error` event (`invalid_stream`, `stream_failed`). An unknown stepper answers `404` before the stream starts. Brain does not use this route yet (it calls `/control`).

## Layout

```text
main.py                  entry point (calls main_flow)
main_flow/               .env, config, logging init, uvicorn, graceful shutdown (stops the motors)
composition_root/        the only place concrete adapters are wired together (driver choice, app, CORS, tracing)
infrastructure/          config, HTTP (inbound: handler, envelope, error mapper, NDJSON decoder/encoder) and motor drivers (outbound: mock, TMC2209)
application/             use-case service (per-motor locks), ports, DTOs, application errors
domain/                  Movement, unit conversions (rotations/rpm to steps), validation
tests/                   domain, application, infrastructure, composition_root, architecture; simple_integration.py is a script
test/                    hardware scripts (simple_rotation_test.py, tmc2209_diagnostic.py, very_simple.py): need real motors
```

Dependencies point inward only (`infrastructure -> application -> domain`); `tests/architecture/` enforces this. Not code of this service: `stepper_config.json` (nothing reads it), `CODEX.md` and `GEMINI.md` (old AI notes), `docs/README_*.md` (copies of other services' docs, bannered), `docs/MICROSERVICE_CONTRACTS.md` (a historical Brain report).

On graceful shutdown the app lifespan and `main_flow` call `stop_and_cleanup()`: the TMC2209 driver disables all enable pins, cancels active step loops and calls `GPIO.cleanup()`. Keep that path intact.

## Tests

```powershell
$env:MOCK_HARDWARE = "1"
windows\Scripts\python.exe -m pytest
```

Result on 2026-10-01: `69 passed` in 3 s with the mock driver. ruff (microphone venv) and mypy report no issues for the application code. **Nothing here proves the real TMC2209/GPIO path works**: that needs a Raspberry Pi and the motors (the `test/` scripts, run only with the owner's agreement).
