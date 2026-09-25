# CLAUDE.md: stepper_microservice

Port **8005**. Python/FastAPI. Drives the stepper motors: two independent arms of the robot. Status: working, needs retest after recent changes. See `README.md` and `../CLAUDE.md`.

Current state (2026-09-22): branch **`feature_code_revision`** (not `feature_ai_claude`), 34 uncommitted files (DTOs and mappers, `service.py`, container/dependency wiring, outbound adapters, `main.py`, `runtime/`, requirements, README, `.env`/`.env.example`, `tests/`), 12 of them untracked. Last commit "stable". Look at `git status` before editing so unrelated work isn't mixed in.

## Role

**Only Brain will call this service** (planned, from the ai-agent's decisions). Nothing calls it yet.

| Path | Use |
|---|---|
| `POST /control/{stepper_id}/rotate` | `rotations`, `rpm`, `direction` |
| `POST /control/{stepper_id}/steps` | `value`, `speed`, `direction` |
| `POST /control/{stepper_id}/stop` | Emergency stop |
| `POST /process/stream/{stepper_id}/set` | NDJSON commands while the request is open. **Not implemented**: `StepperService.execute_stream` reads and discards every event (`# In a real implementation, parse event...`); it only reports success/failure of opening the stream |
| `GET /health` | Liveness |
| `GET /available` | Whether the outbound motor driver (mock or TMC2209/GPIO) initialized; does not pulse a motor |

Motors are configured in `STEPPER_CONFIGS` (JSON: id → BCM pins `step`, `dir`, `en`), e.g. `stepper_1` and `stepper_2` for the two arms. Also `SERVICE_HOST/PORT`, `ALLOWED_ORIGINS`, `STEPS_PER_REVOLUTION` (400 in `.env.example`), `DEFAULT_SPEED_LIMIT`, `MOCK_HARDWARE=1`. Each motor has its own async lock, so commands never overlap on the same motor.

## Layout

`main.py` → `composition_root/` → `application/` (`StepperService`, ports, DTOs, mappers) → `infrastructure/inbound/http/fastapi_adapter.py` and `infrastructure/outbound/` (`tmc2209_adapter.py` real hardware via `RPi.GPIO`, `mock_adapter.py`). Real hardware only works on a Raspberry Pi. Elsewhere it falls back to the mock. `runtime/environment.py` is **real code** (resolves `APP_ENV`/`VSCODE_ENV`).

Not real code: `test/` (three hardware scripts: `simple_rotation_test.py`, `tmc2209_diagnostic.py`, `very_simple.py`), `stepper_config.json` (nothing reads it), `CODEX.md`/`GEMINI.md` (old AI notes), and `docs/README_*.md` (copies of the microphone, speaker, STT and TTS docs, not this service's).

## Rules

- **Safety:** never move real motors without asking the user first, and respect step and speed limits. Prefer `MOCK_HARDWARE=1` for tests.
- The shutdown path must always disable the enable pins and call `GPIO.cleanup()`. Do not break it.
- Uses `shared_logging` (`init_logging("stepper", ...)`, `-e ../shared-logging` in requirements). Since 2026-09-22 it also uses `contracts` (`./vendor/contracts_microservice-0.8.0-py3-none-any.whl`): `/health`, `/available` and the three `/control/{id}/...` batch routes answer with `contracts.api.common.envelope.ApiEnvelope`, `data` built from `contracts.api.microservices.stepper.batch.StepperBatchResult` / `contracts.api.microservices.common`. The routes and their inbound DTOs (query params, not a JSON body) did not change, only the response envelope. `contracts.stream` gained registered `STEPPER_INBOUND`/`STEPPER_OUTBOUND` schemas, but `/process/stream/{id}/set` itself still doesn't use the codec or do anything with what it receives (see the API table above) — that's a separate, unstarted piece of work.
- Git hygiene: the repo tracks `.env` and `.env.example` and has no `.gitignore`. `.env` only holds pin numbers today. Never put secrets in it, and tell the user before adding a `.gitignore`.
- The venv was bare (only pytest, `shared-logging`, now `contracts`; no ruff, no mypy). It still has no FastAPI/uvicorn/pydantic installed even though `requirements.windows.txt` lists them: those pins (`pydantic==2.7.4`, `fastapi==0.111.0`) predate prebuilt wheels for Python 3.14 and fail to build from source without a Rust toolchain (`pip install -r requirements.windows.txt` fails on `pydantic-core`). Bumping the pins is real, deliberate work someone should do on purpose, not a side effect of an unrelated change — for now, install unpinned (`pip install --only-binary=:all: fastapi uvicorn pydantic`) to get a working venv for local dev/tests.

## Commands

```powershell
$env:MOCK_HARDWARE = "1"
& windows\Scripts\python.exe main.py
& windows\Scripts\python.exe -m pytest tests     # collects tests/test_tracing.py and tests/test_http_envelope.py; simple_integration.py is a script
```
