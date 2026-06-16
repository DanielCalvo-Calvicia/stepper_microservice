# Codex Module Generation Context

This file captures the reusable structure shared by the existing module documentation in `docs/`.
Use it as durable context when generating a new module in the same style. Keep the generated module abstractly consistent with these patterns, while replacing only the documented variation points.

## 1. General Module Pattern

The modules are small Python FastAPI microservices with a lightweight hexagonal / ports-and-adapters structure.

Common responsibility pattern:

- Expose a narrow HTTP API for one capability.
- Keep the application service mostly framework-neutral.
- Put protocol handling in an inbound FastAPI adapter.
- Put hardware, model, provider, filesystem, or external-system behavior in outbound adapters.
- Use DTOs and mappers to move data across boundaries.
- Build all concrete dependencies in a composition root.
- Start through `main.py` and Uvicorn.

Consistent parts:

- Public HTTP interface.
- Health endpoint.
- Optional availability/readiness-style endpoint.
- Streaming and/or batch processing endpoints.
- Application service layer.
- Inbound, service, and outbound DTOs.
- Mapper functions between layers.
- Abstract ports.
- Concrete infrastructure adapters.
- Environment-based configuration.
- Startup/shutdown lifecycle.
- Failure, security, and transfer notes.
- Manual or pytest-style tests.

Parts that vary:

- The business capability.
- Endpoint set and request/response payloads.
- Whether the module processes batch data, streaming data, or both.
- Whether streams are direct, decoupled through set/get endpoints, or autoloaded from an external source.
- The concrete outbound dependency.
- Runtime state requirements.
- Validation rules.
- Test depth.

## 2. Shared Functional Areas

Inputs:

- HTTP requests through FastAPI.
- Query parameters for runtime options.
- Raw request bodies for bytes or text.
- Streaming request bodies for long-running input.
- Optional background/autoload inputs from configured URLs.
- Environment variables and `.env` files for configuration.

Outputs:

- JSON response envelopes for normal control-plane responses.
- Streaming responses for incremental output.
- NDJSON or SSE-style event streams depending on module role.
- Base64-encoded binary payloads when binary data crosses JSON boundaries.
- Status/availability responses.

Configuration:

- `SERVICE_HOST` and `SERVICE_PORT`.
- Provider/backend selection values.
- Adapter-specific settings.
- Optional external stream URLs.
- Device, model, timeout, or provider credentials.
- Launch/profile configuration through `.vscode` and `.env`.

Validation:

- Basic positive numeric checks.
- Required body checks.
- Required secret/backend checks during startup or adapter creation.
- Stream event shape validation where consumers depend on structured events.
- HTTP status validation for external service calls.
- Payload format validation for JSON, base64, text, bytes, or stream events.

Core logic:

- Thin application orchestration.
- Mapping inbound DTOs to service DTOs.
- Delegating specialized work to outbound adapters.
- Returning response DTOs back through mapper layers.
- Managing stream queues/tasks when decoupled streaming is used.

State or data handling:

- Usually no persistent database.
- Runtime state is process-local.
- Common state includes active stream/task references, async queues, selected backend/device, setup futures, and current configuration.
- Temporary files may be used by specific outbound adapters.
- Stream state is represented with sequence numbers, timestamps, event types, and payloads.

External dependencies:

- FastAPI and Uvicorn.
- `httpx` for outbound HTTP or autoload workers.
- Provider SDKs, local engines, model runtimes, or hardware libraries depending on module.
- Optional OS/runtime resources.
- Checked-in or local virtual environment artifacts are documented but are not part of the reusable module source pattern.

Error handling:

- Route handlers usually catch exceptions and return JSON errors.
- Streaming handlers may emit structured error events after streaming starts.
- Startup failures are allowed to prevent the service from running when required dependencies are missing.
- Cleanup is attempted during shutdown or after failed workflows.
- Avoid broad exception handling when a more specific error path is practical.

Logging or observability:

- Centralized logger setup appears in startup flow.
- Health and availability endpoints serve as basic observability.
- Runtime logs are expected around startup, shutdown, adapter selection, and failures.
- Metrics and tracing are optional; they are not part of the common baseline.

Tests:

- Manual integration scripts are common.
- Some modules include pytest contract tests.
- Tests generally target health, availability, streaming contracts, endpoint behavior, and invalid inputs.
- Coverage may be uneven in older modules; new modules should improve coverage around their wire contract.

Documentation:

- Each module should have a technical README.
- Common README sections include overview, architecture, repository structure, runtime flow, ports/interfaces, data model, configuration, dependencies, state, failure recovery, security, transfer notes, and unknowns.

## 3. Common Types and Structures

### Stream Event Object

Generic purpose: standardize streaming data across services.

Common fields:

- `type`
- `sequence`
- `timestamp`
- `payload`

Common usage:

- Emitted as NDJSON lines or SSE `data:` payloads.
- Used for stream start, partial output, completion, heartbeat, and error reporting.

Fixed parts:

- Required fields.
- Monotonically increasing sequence per HTTP stream.
- UTC timestamp.
- Object payload.

Variable parts:

- Event types supported by the module.
- Payload fields.
- Completion reasons.
- Binary vs text content.

### JSON Response Envelope

Generic purpose: provide a consistent wrapper for control-plane HTTP responses.

Common fields:

- `action`
- `status`
- `status_code`
- `message`
- `timestamp`
- `data`

Common usage:

- Health responses.
- Availability responses.
- Setup or accepted responses.
- Batch responses.
- Error responses.

Fixed parts:

- Status/message metadata and `data` container.

Variable parts:

- `action` names.
- Success messages.
- `data` shape.

### Configuration DTOs

Generic purpose: carry startup/runtime settings into adapters.

Common responsibilities:

- Store inbound adapter config.
- Store outbound adapter config.
- Represent optional URLs, credentials, backend names, device/model options, CORS origins, or timeouts.

Common usage:

- Created in the composition root.
- Passed to concrete adapter constructors.

Fixed parts:

- Separate init/config DTOs per boundary.

Variable parts:

- Fields needed by the selected backend.

### Request DTOs

Generic purpose: represent input at inbound, service, and outbound layers.

Common fields or responsibilities:

- Body data, stream data, or request marker.
- Query/runtime options.
- Processing parameters.
- Optional setup acknowledgement primitives for streaming setup.

Common usage:

- Constructed by HTTP adapter.
- Mapped into service DTOs.
- Mapped into outbound DTOs when needed.

Fixed parts:

- Immutable dataclass-style objects.
- One DTO family per operation.

Variable parts:

- Payload type.
- Operation-specific options.
- Defaults.

### Response DTOs

Generic purpose: represent operation results independent of HTTP.

Common fields or responsibilities:

- `success` flag.
- `message`.
- Output stream.
- Output data.
- Availability boolean.
- Accepted boolean.
- Cleanup status.

Common usage:

- Returned by service and outbound layers.
- Mapped back to inbound/HTTP response format.

Fixed parts:

- Explicit response object per operation.

Variable parts:

- Actual result fields.

### Port Interfaces

Generic purpose: define contracts between layers.

Common interfaces:

- Inbound adapter port.
- Service port.
- Outbound adapter port.

Common usage:

- Application service depends on outbound port abstractions.
- Composition root wires concrete adapters.

Fixed parts:

- Abstract method boundary style.

Variable parts:

- Operation method names and signatures.

### Mapper Functions

Generic purpose: convert DTOs between adapter, service, and outbound layers.

Common behavior:

- Mostly direct field copies.
- Useful extension points if DTOs diverge.

Common usage:

- Called by inbound adapter and service layer.

Fixed parts:

- Mapper modules under DTO structure.
- Directional mapper names.

Variable parts:

- Transformations when layer-specific DTOs diverge.

### Application Service Class

Generic purpose: own use-case orchestration and validation.

Common responsibilities:

- Validate inputs.
- Coordinate tasks/queues when needed.
- Call outbound adapter.
- Return service DTOs.

Fixed parts:

- Framework-neutral service methods.

Variable parts:

- Business rules and processing flow.

### Inbound FastAPI Adapter

Generic purpose: own HTTP route registration and protocol conversion.

Common responsibilities:

- Register routes.
- Parse requests.
- Construct inbound DTOs.
- Call service.
- Format JSON or streaming responses.

Fixed parts:

- Route registration centralized in the adapter.

Variable parts:

- Paths.
- Media types.
- Request parsing.
- Stream encoding.

### Outbound Adapter

Generic purpose: implement the concrete capability.

Common responsibilities:

- Talk to an external provider, local engine, hardware, filesystem, or HTTP source.
- Hide backend-specific details behind the outbound port.

Fixed parts:

- Implements outbound port.

Variable parts:

- Backend implementation and failure modes.

### Container and Dependency Objects

Generic purpose: hold the assembled dependency graph.

Common fields or responsibilities:

- Top-level container name.
- Service-specific dependency bundle.
- Inbound adapter.
- Service.
- Outbound adapter.

Common usage:

- Built by `BuildContainer()` during startup.

Fixed parts:

- Composition root owns construction.

Variable parts:

- Dependency bundle name.
- Adapter selection logic.

### Background Worker or Autoloader

Generic purpose: optional background ingestion from a configured external stream.

Common responsibilities:

- Store source URL/config.
- Own an async task handle.
- Provide start/stop methods.
- Reconnect or cancel cleanly.

Common usage:

- Started from FastAPI lifespan when configured.

Fixed parts:

- Optional component, not required for baseline module.

Variable parts:

- Source protocol and processing path.

## 4. Common File or Folder Organization

Common layout:

```text
.
|-- main.py
|-- requirements*.txt
|-- .env / .env.example
|-- .vscode/
|-- application/
|   |-- dtos/
|   |   |-- adapter_inbound_dtos.py
|   |   |-- adapter_outbound_dtos.py
|   |   |-- services_dtos.py
|   |   `-- mapper/
|   |-- ports/
|   |   |-- adapter_inbound_port.py
|   |   |-- adapter_outbound_port.py
|   |   `-- service_port.py
|   `-- services/
|       `-- service.py
|-- composition_root/
|   |-- containers/
|   |   `-- container.py
|   |-- dependencies/
|   |   `-- <module>_dependency.py
|   `-- setup/
|       `-- setup.py
|-- infrastructure/
|   |-- inbound/
|   |   `-- http/
|   |       |-- fastapi_adapter.py
|   |       `-- optional_background_worker.py
|   `-- outbound/
|       `-- concrete_adapter.py
|-- tests/
|   |-- simple.py
|   `-- optional_contract_tests.py
`-- docs or README files
```

Generic categories:

- Public entry point: `main.py`.
- Runtime setup: `composition_root/setup`.
- Dependency assembly: `composition_root/containers` and `composition_root/dependencies`.
- Application core: `application/services`, `application/ports`, `application/dtos`.
- Inbound implementation: `infrastructure/inbound/http`.
- Outbound implementation: `infrastructure/outbound`.
- Configuration: `.env`, `.env.example`, `.vscode`, requirements files.
- Tests: `tests/`, usually manual integration plus optional pytest contract tests.
- Documentation: technical README and contract notes.

Do not treat a checked-in virtual environment such as `windows/` as reusable source structure.

## 5. Common Lifecycle or Workflow

Initialization:

1. `main.py` resolves environment/logging.
2. `asyncio.run(setup())` starts the async bootstrap.
3. `.env` and process environment are loaded.
4. Host and port are read.
5. `BuildContainer()` creates the module dependency graph.
6. Dependency factory reads module-specific configuration.
7. Outbound adapter is instantiated.
8. Application service is instantiated.
9. FastAPI app is created.
10. Inbound adapter registers routes.
11. Uvicorn starts serving.

Input preparation:

1. Route receives HTTP input.
2. Query parameters and body/stream are parsed.
3. Inbound DTO is constructed.
4. Raw data may be converted to async iterators, decoded text, bytes, or structured events.

Validation:

1. Route-level validation handles missing/invalid request shapes.
2. Service-level validation handles generic business constraints.
3. Adapter-level validation handles backend-specific constraints.
4. Stream consumers validate event shape where required.

Main execution:

1. Inbound adapter maps request DTO to service DTO.
2. Service may map to outbound DTO.
3. Service delegates to outbound adapter.
4. Outbound adapter performs the concrete operation.
5. Result flows back through response DTOs and mappers.

Data transformation:

- Raw HTTP bodies become DTO fields or async streams.
- Internal streams become NDJSON or SSE events.
- Binary data is base64 encoded when placed in JSON.
- Text/binary outputs are wrapped in response envelopes or stream events.

Result generation:

- Immediate operations return JSON.
- Streaming operations return `StreamingResponse`.
- Decoupled operations may use `POST /.../set` to feed input and `GET /.../get` to drain output.
- Batch operations return a completed result in one response.

Error handling:

- Pre-stream failures usually return JSON errors.
- Mid-stream failures can emit structured `error` events.
- External dependency failures are surfaced as unavailable, invalid response, auth, or internal errors.
- Cleanup may be attempted after partial startup or stream failure.

Cleanup:

- Uvicorn/FastAPI lifespan manages normal shutdown.
- Background workers are cancelled.
- Active streams/tasks/resources are closed when implemented.
- Setup-level cleanup hook exists, even if minimal.

## 6. Variation Points

Usually changes per module:

- Domain/capability name.
- Default port.
- HTTP endpoint set.
- Request body type: raw bytes, text, JSON, NDJSON, SSE, or stream.
- Response body type: JSON, NDJSON, SSE, base64 payload, or live stream.
- DTO class names and fields.
- Service method names.
- Outbound adapter implementation.
- External provider, local engine, hardware dependency, or upstream/downstream service.
- Environment variable names and defaults.
- Validation rules.
- Runtime state requirements.
- Whether an availability endpoint exists.
- Whether batch mode exists.
- Whether direct streaming exists.
- Whether decoupled set/get streaming exists.
- Whether background autoload exists.
- Error status policy.
- Test scripts and contract tests.
- Security concerns and secret requirements.
- Technical debt and unknowns.

Should remain stable:

- Layered architecture.
- Composition root wiring.
- DTO and mapper pattern.
- Port abstraction pattern.
- FastAPI inbound adapter pattern.
- Environment-driven startup.
- Health endpoint.
- Structured response/event conventions.
- README/documentation shape.

## 7. Reusable Module Template

Suggested responsibilities:

- Provide one bounded microservice capability.
- Expose HTTP endpoints for health, optional availability, and the main operation.
- Keep protocol handling in the inbound adapter.
- Keep orchestration in the service layer.
- Keep concrete backend behavior in outbound adapters.
- Represent cross-layer data using immutable DTOs.
- Use mappers as boundary extension points.

Suggested components:

- `main.py`
- `composition_root/setup/setup.py`
- `composition_root/containers/container.py`
- `composition_root/dependencies/<module>_dependency.py`
- `application/ports/adapter_inbound_port.py`
- `application/ports/service_port.py`
- `application/ports/adapter_outbound_port.py`
- `application/dtos/adapter_inbound_dtos.py`
- `application/dtos/services_dtos.py`
- `application/dtos/adapter_outbound_dtos.py`
- `application/dtos/mapper/*.py`
- `application/services/service.py`
- `infrastructure/inbound/http/fastapi_adapter.py`
- `infrastructure/outbound/<backend>_adapter.py`
- `tests/simple.py`
- Optional contract tests.
- Technical README.

Generic type categories:

- Init/config DTOs.
- Operation request DTOs.
- Operation response DTOs.
- Availability DTOs.
- Cleanup DTOs.
- Stream event schema.
- Container/dependency dataclasses.
- Port interfaces.
- Mapper functions.

Generic workflow:

```text
HTTP request
  -> FastAPI route
  -> inbound DTO
  -> inbound-to-service mapper
  -> application service
  -> service-to-outbound mapper
  -> outbound adapter
  -> outbound response DTO
  -> service response DTO
  -> service-to-inbound mapper
  -> JSON or streaming HTTP response
```

Expected extension points:

- Add fields to DTOs.
- Add mapper transformations.
- Swap outbound adapters.
- Add validation in service layer.
- Add optional background worker.
- Add batch or stream endpoint variants.
- Add contract tests for wire formats.
- Add provider-specific config in dependency factory.

Minimum required pieces:

- `main.py`.
- Composition root setup.
- Container/dependency factory.
- FastAPI inbound adapter.
- Service port and service implementation.
- Outbound port and one concrete adapter.
- DTOs for each exposed operation.
- Mappers between layers.
- Health endpoint.
- Environment configuration.
- At least one runnable test or smoke script.
- README describing architecture, runtime flow, interfaces, config, failures, and unknowns.

Optional pieces:

- Availability endpoint.
- Batch endpoint.
- Direct stream endpoint.
- Decoupled set/get stream endpoints.
- Background/autoload worker.
- Contract tests.
- OpenAPI customization.
- Cleanup/lifespan hooks.
- Multiple outbound backends.
- Docker/CI configuration.
- Metrics/tracing/authentication.

## 8. Guidelines for Generating a New Module

Preserve the common structure:

- Use the same top-level folders.
- Keep `application` independent of concrete infrastructure as much as possible.
- Keep FastAPI-specific code inside `infrastructure/inbound/http`.
- Keep backend-specific code inside `infrastructure/outbound`.
- Build concrete instances only in `composition_root`.

Replace only variation points:

- Rename module-specific dependency files, service classes, DTOs, and endpoint actions.
- Change request/response fields to fit the new capability.
- Change outbound adapter implementation.
- Change environment variable names and defaults.
- Change validation rules and processing steps.

Follow naming and organization conventions:

- Use request/response DTO pairs.
- Use `Init...Dto` for configuration.
- Use clear operation names across inbound, service, and outbound layers.
- Keep mapper names directional.
- Keep route registration centralized in the FastAPI adapter.

Keep helper patterns consistent:

- Prefer DTO mapping over passing raw HTTP objects into the service.
- Prefer async iterators for streaming data.
- Use structured stream events instead of sentinel strings.
- Use JSON envelopes for control-plane responses.
- Use base64 for binary data inside JSON events.
- Use FastAPI lifespan for background worker startup/shutdown.

Add tests matching the common style:

- Health endpoint test.
- Availability test if present.
- Main endpoint test.
- Stream contract test if streaming is used.
- Error-path test for invalid input.
- Adapter contract tests for external dependencies where possible.
- Keep manual integration scripts separate from automated pytest tests.

Avoid overfitting:

- Do not copy business logic from unrelated modules.
- Do not reuse domain-specific field names unless the new module truly needs them.
- Do not hardcode ports, provider names, model names, device names, or external URLs from another module.
- Do not assume every module needs batch, streaming, decoupled streaming, or autoload.
- Do not preserve known architectural leaks unless compatibility requires them.

## 9. Ambiguities and Missing Information

- Test coverage is inconsistent, so the exact expected automated test baseline is unclear.
- Some cleanup hooks are placeholders; the required cleanup depth for a new module is not fully established.
- Authentication and authorization are mostly absent, so security expectations are minimal but not necessarily intentional.
- Observability is limited to logs and health endpoints; no shared metrics/tracing standard is visible.
- Error handling style varies, especially around broad exception catching and status codes.
- Streaming format differs by role: NDJSON is common, SSE appears where text/event compatibility is needed.
- Some modules use direct streams, others use decoupled set/get flows, and not every module supports both.
- Persistent storage is generally absent, but there is not enough evidence to say future modules must avoid it.
- Runtime environment handling includes `.env`, `.vscode`, and process variables, but the precedence rules are not fully uniform across all modules.
- Some docs mention generated or local artifacts such as checked-in virtual environments; these should not be treated as required source structure for new modules.

## Generation Checklist

When generating a new module, use this checklist:

1. Define the new module capability and variation points.
2. Choose endpoint set: health, optional availability, batch, direct stream, decoupled stream, autoload.
3. Define request/response DTO families for inbound, service, and outbound layers.
4. Define port interfaces matching the chosen operations.
5. Implement mapper functions, starting with direct field copies.
6. Implement service validation and orchestration.
7. Implement one concrete outbound adapter.
8. Implement FastAPI route registration and HTTP response formatting.
9. Wire dependencies in `composition_root`.
10. Add environment defaults and example config.
11. Add tests for health, main operation, invalid input, and stream contract if relevant.
12. Add technical README with the common documentation sections.

