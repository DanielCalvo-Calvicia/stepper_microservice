# CLAUDE.md: stepper_microservice

Port **8005** (`SERVICE_PORT`). Python/FastAPI. Drives the stepper motors: two independent arms of the robot. Status: working, needs retest on the Pi. See `README.md` and `../CLAUDE.md`.

Current state (2026-10-01): branch `feature_ai_claude_2` (tracks `origin/feature_ai_claude_2`). HEAD `372d197` is the old structure; **the restructure below is uncommitted**. It was rewritten to the layered layout of microphone/stt/tts/speaker and now uses `contracts` 0.10.0 (`STEPPER_INBOUND/OUTBOUND`) for its stream route. Other uncommitted files: the tracked `.env` (modified, deliberately not committed), the bannered `docs/README_*.md`, tracked `.pyc` noise. Tests: `69 passed` with `MOCK_HARDWARE=1`; ruff and mypy clean on the application code. The real GPIO path was never run here (needs a Raspberry Pi and the motors).

## Role

**Only Brain calls this service**, on the batch `/control/{id}/...` routes, from the ai-agent's movement decisions.

| Path | Use |
|---|---|
| `POST /control/{stepper_id}/rotate` | query: `rotations`, `rpm`, `direction` |
| `POST /control/{stepper_id}/steps` | query: `value`, `speed`, `direction` |
| `POST /control/{stepper_id}/stop` | Emergency stop (bypasses the busy lock) |
| `POST /process/stream/{stepper_id}/set` | NDJSON `STEPPER_INBOUND` commands (`stream_started`, `partial` per command, `completed`), answered with `STEPPER_OUTBOUND` events (`stream_started`, one `partial` result per command, `completed` or `error`). Executes the commands in order; a failed command ends the stream. Brain does not use it yet |
| `GET /health` | Liveness |
| `GET /available` | Whether the motor driver (mock or TMC2209/GPIO) initialized; does not pulse a motor |

Answers use `ApiEnvelope`; `data = StepperBatchResult`, also on failures. Errors: 404 unknown stepper, 409 busy motor, 422 invalid command, 502 driver failed, else 500 (Brain treats any non-200 as a failed move). Each motor has its own async lock: a busy motor rejects, it does not queue.

Motors are configured in `STEPPER_CONFIGS` (JSON: id -> BCM pins `step`, `dir`, `en`). Other env: `SERVICE_NAME`, `SERVICE_HOST/PORT`, `LOG_LEVEL`, `ALLOWED_ORIGINS`, `DEFAULT_SPEED_LIMIT` (1000.0), `STEPS_PER_REVOLUTION` (400), `MOCK_HARDWARE=1` (only the string `1` counts).

## Layout

Same layered layout as the other services: `main.py` -> `main_flow/http.py` -> `composition_root/` (containers, `stepper_dependencies.py`) -> `application/` (`StepperService`, ports, DTOs, errors) -> `domain/` (`Movement`, `operations/conversion.py`) -> `infrastructure/` (`config/`, `inbound/http/`, `outbound/mock_motor/`, `outbound/tmc2209/`). `tests/architecture/` enforces that dependencies point inward. Real hardware only works on a Raspberry Pi; elsewhere it falls back to the mock driver.

Not real code: `test/` (hardware scripts: `simple_rotation_test.py`, `tmc2209_diagnostic.py`, `very_simple.py`), `tests/simple_integration.py` (a script against a running service), `stepper_config.json` (nothing reads it), `CODEX.md`/`GEMINI.md` (old AI notes), `docs/README_*.md` (copies of other services' docs; bannered), `docs/MICROSERVICE_CONTRACTS.md` (historical Brain report).

## Rules

- **Safety:** never move real motors without asking the user first, and respect step and speed limits. Use `MOCK_HARDWARE=1` for tests.
- The shutdown path must always disable the enable pins and call `GPIO.cleanup()` (`StepperService.stop_and_cleanup`, run by the app lifespan and by `main_flow`). Do not break it.
- Events come from `contracts.stream` through the codec, never hand-written JSON. `contracts` comes from `vendor/contracts_microservice-<version>.whl` (0.10.0); refresh it with `contracts/scripts/bundle.py`. New stepper events go into `contracts` first.
- Uses `shared_logging` (`init_logging("stepper")` in `main_flow/http.py`, `-e ../shared-logging` in requirements). Messages are constant strings with keyword fields.
- Git hygiene: the repo tracks `.env` and `.env.example` and has no `.gitignore`. `.env` only holds pin numbers today. Never put secrets in it, and tell the user before adding a `.gitignore`. Do not commit the modified `.env`.
- `requirements.windows.txt` uses lower bounds (the old pins have no Python 3.14 wheels); `requirements.linux.txt` keeps mostly exact pins and `RPi.GPIO` for the Pi. Ruff/mypy/black are configured in `pyproject.toml` but not installed in this venv (use the microphone venv's).

## Commands

```powershell
$env:MOCK_HARDWARE = "1"
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest           # 69 tests, ~3 s, mock driver
```
