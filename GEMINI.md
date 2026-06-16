# Gemini Code Generation & Architecture Rules for Microservices

This document defines the rules, naming conventions, directory structures, and code patterns for microservices in this repository. AI agents (such as Gemini/Antigravity) must follow these guidelines strictly when creating, modifying, or refactoring microservices.

---

## 1. Core Architectural Principles

All microservices are designed using **Hexagonal Architecture (Ports and Adapters)**. This enforces strict separation of concerns, decoupling domain logic from both inbound protocols (e.g., FastAPI/HTTP) and outbound infrastructures (e.g., hardware devices, AI models, filesystems, external APIs).

```
                 +-----------------------------------------+
                 |            Inbound Adapter              |
                 |       (e.g., http/fastapi_adapter.py)    |
                 +-------------------+---------------------+
                                     |
                                     v [Inbound Port / DTOs]
                 +-------------------+---------------------+
                 |           Application Service           |
                 |          (e.g., services/service.py)    |
                 +-------------------+---------------------+
                                     |
                                     v [Outbound Port / DTOs]
                 +-------------------+---------------------+
                 |            Outbound Adapter             |
                 |      (e.g., outbound/concrete_adapter.py)|
                 +-----------------------------------------+
```

### Layer Responsibilities
*   **Application Core (`application/`)**:
    *   **Ports (`ports/`)**: Abstract Base Classes (ABCs) that define interface contracts. No framework-specific or hardware-specific imports allowed.
    *   **Services (`services/`)**: Coordinate use cases, enforce framework-neutral validation, and delegate concrete operations to outbound adapters.
    *   **DTOs (`dtos/`)**: Immutable, type-safe data containers (`@dataclass(slots=True, frozen=True)`) used to pass data across boundaries.
    *   **Mappers (`dtos/mapper/`)**: Pure functions that transform DTOs from one layer's structure to another.
*   **Infrastructure Layer (`infrastructure/`)**:
    *   **Inbound (`inbound/`)**: Protocol handlers (e.g., FastAPI, WebSocket adapters). Responsible for parsing HTTP requests, constructing inbound DTOs, calling the service layer, mapping responses, and managing the stream/event wire formats.
    *   **Outbound (`outbound/`)**: Hardware, model, provider, or database integrations. Implements the outbound ports defined by the application layer.
*   **Composition Root (`composition_root/`)**:
    *   The single place where all components are instantiated and wired together.
    *   Contains the dependency graph, environment parsing, and startup/shutdown lifecycle hooks.

---

## 2. Standard Directory Layout

Every microservice must strictly conform to the following directory layout:

```text
.
|-- main.py                               # Service process entrypoint
|-- requirements.windows.txt              # Windows dependency file
|-- requirements.linux.txt                # Linux dependency file
|-- .env                                  # Local environment configuration
|-- .env.example                          # Reference configuration template
|-- application/
|   |-- dtos/
|   |   |-- adapter_inbound_dtos.py       # DTOs entering the inbound adapter
|   |   |-- adapter_outbound_dtos.py      # DTOs exiting/entering the outbound adapter
|   |   |-- services_dtos.py              # DTOs used within the application core
|   |   `-- mapper/
|   |       |-- adapter_inbound_to_service.py
|   |       |-- service_to_adapter_inbound.py
|   |       |-- service_to_adapter_outbound.py
|   |       `-- adapter_outbound_to_service.py
|   |-- ports/
|   |   |-- adapter_inbound_port.py       # Abstract inbound interface
|   |   |-- adapter_outbound_port.py      # Abstract outbound interface
|   |   `-- service_port.py               # Abstract service interface
|   `-- services/
|       `-- service.py                    # Concrete application service logic
|-- composition_root/
|   |-- containers/
|   |   `-- container.py                  # Global application container
|   |-- dependencies/
|   |   `-- <module>_dependency.py        # Module-specific dependency factory
|   `-- setup/
|       `-- setup.py                      # Server bootstrap and lifecycle
|-- infrastructure/
|   |-- inbound/
|   |   `-- http/
|   |       |-- fastapi_adapter.py        # FastAPI inbound implementation
|   |       `-- optional_worker.py        # Background stream consumer/worker
|   `-- outbound/
|       `-- <backend>_adapter.py          # Concrete outbound hardware/service adapter
|-- tests/
|   |-- simple.py                         # Manual integration/smoke tests
|   `-- test_*.py                         # Automated pytest suite
`-- README.md                             # Technical documentation
```

---

## 3. Implementation Patterns & Boilerplates

### 3.1 DTOs (`application/dtos/`)
DTOs must use Python's `@dataclass` decorator with `slots=True` and `frozen=True` to ensure immutability and performance.

```python
from dataclasses import dataclass
from typing import AsyncIterator
import asyncio

@dataclass(slots=True, frozen=True)
class InitInboundAdapterDto:
    allow_origins: tuple[str, ...] = ("*",)
    autoload_stream_url: str | None = None

@dataclass(slots=True, frozen=True)
class StartStreamRequestDto:
    stream: AsyncIterator[bytes]
    setup_future: asyncio.Future[Any] | None = None
```

### 3.2 Ports (`application/ports/`)
Ports must inherit from `abc.ABC` and use the `@abstractmethod` decorator.

```python
from abc import ABC, abstractmethod
from typing import Any

class AdapterInboundPort(ABC):
    @abstractmethod
    async def process(self, request: Any) -> Any:
        pass

    @property
    @abstractmethod
    def get_app(self) -> Any:
        """Return the underlying framework application instance (e.g., FastAPI app)."""
        pass
```

### 3.3 Mappers (`application/dtos/mapper/`)
Mappers must be pure functions. They should contain no business logic, only data transformation, with trace-level logging.

```python
from application.dtos.services_dtos import ServiceRequestDto
from application.dtos.adapter_inbound_dtos import InboundRequestDto
from runtime.logger import get_logger

logger = get_logger("application.mapper.inbound_to_service")

def map_inbound_to_service_request(request: InboundRequestDto) -> ServiceRequestDto:
    logger.trace("Mapping inbound DTO to service DTO")
    return ServiceRequestDto(
        payload=request.payload,
        setup_future=request.setup_future,
    )
```

### 3.4 Application Service (`application/services/`)
Services implement the service port and call the outbound port. They handle pure, framework-neutral business validation.

```python
from application.ports.service_port import MyServicePort
from application.ports.adapter_outbound_port import AdapterOutboundPort
from runtime.logger import get_logger

logger = get_logger("application.service")

class MyService(MyServicePort):
    def __init__(self, outbound_port: AdapterOutboundPort):
        self.outbound_port = outbound_port

    async def execute(self, request: ServiceRequestDto) -> ServiceResponseDto:
        logger.info("Executing service request")
        if not request.payload:
            return ServiceResponseDto(success=False, message="Empty payload")
        return await self.outbound_port.send(request)
```

### 3.5 Inbound FastAPI Adapter (`infrastructure/inbound/http/`)
The inbound adapter implements `AdapterInboundPort`, instantiates routes, parses HTTP/Stream boundaries, and handles exceptions.

> [!IMPORTANT]
> Keep route definition registration centralized inside the Inbound Adapter class constructor or a registration method. Do not scatter routes across files.

```python
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
import time
from application.ports.adapter_inbound_port import AdapterInboundPort
from application.ports.service_port import MyServicePort

class FastApiAdapter(AdapterInboundPort):
    def __init__(self, service_port: MyServicePort, app: FastAPI):
        self.service_port = service_port
        self.app = app
        self.register_routes(self.app)

    def register_routes(self, app: FastAPI) -> None:
        @app.get("/health", tags=["Health"])
        async def health_check() -> JSONResponse:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "action": "health_check",
                    "status": "success",
                    "status_code": status.HTTP_200_OK,
                    "message": "Microservice is healthy",
                    "timestamp": time.time(),
                    "data": {"status": "ok"}
                }
            )
```

---

## 4. Standard Protocols and Envelopes

### 4.1 JSON Response Envelope
All non-streaming HTTP control-plane responses (including errors and health checks) must use the following standard JSON structure:

```json
{
  "action": "action_name",
  "status": "success | error",
  "status_code": 200,
  "message": "Human readable status description",
  "timestamp": 1718375320.12,
  "data": {
    "your_key": "your_value"
  }
}
```

### 4.2 Stream Event Object (NDJSON / SSE)
For streaming outputs or inputs, format individual lines as **Newline-Delimited JSON (NDJSON)** or Server-Sent Events (SSE). Each JSON event line must conform to this schema:

```json
{
  "type": "stream_started | partial | completed | heartbeat | error",
  "sequence": 1,
  "timestamp": "2026-06-14T14:29:00Z",
  "payload": {
    "bytes_base64": "...",
    "text": "...",
    "message": "..."
  }
}
```

*   **`type`**: Indicates the event phase.
*   **`sequence`**: A monotonically increasing integer starting at 1 per HTTP connection stream.
*   **`timestamp`**: ISO-8601 UTC date-time representation ending in `Z`.
*   **`payload`**: Event-specific object payload. If transferring binary data over JSON streams, encode bytes in **base64** and assign to the `bytes_base64` property.

---

## 5. Lifecycle Management

Startup and shutdown transitions must be coordinated cleanly using **FastAPI Lifespan** context managers.

1.  **Startup Flow**:
    *   `main.py` starts the process -> calls `setup()` in `composition_root/setup/setup.py`.
    *   `setup()` loads `.env` configuration.
    *   `BuildContainer()` builds the global container and initializes dependencies.
    *   Outbound adapters initialize connections/drivers.
    *   FastAPI app instance is created with the custom lifespan handler.
    *   Inbound adapter registers routes.
    *   Uvicorn starts listening.
2.  **Lifespan Hook**:
    *   The `app_lifespan` function triggers any background loaders (e.g., autoloader streams).
3.  **Teardown Flow**:
    *   On shutdown signal, Uvicorn stops accepting connections.
    *   Lifespan handler executes teardown sequence.
    *   Autoload background loops are requested to stop and are awaited.
    *   Domain service cleanups (e.g., `service.stop_and_cleanup()`) are triggered, calling down to hardware or connection release hooks on outbound adapters.

---

## 6. Step-by-Step Code Generation Checklist

When instructed to create or extend a microservice module, follow these steps in order:

1.  **Define and Map Variation Points**: Identify the exact domain capability, ports, input type (batch/stream), and outbound target backend.
2.  **Define Ports**: Create abstract port classes under `application/ports/` for inbound, service, and outbound layers.
3.  **Create DTOs**: Create immutable `@dataclass(slots=True, frozen=True)` schemas under `application/dtos/`.
4.  **Create Mappers**: Write pure transformation functions under `application/dtos/mapper/`.
5.  **Implement Service**: Write domain coordination and validation under `application/services/`.
6.  **Implement Outbound Adapter**: Write the concrete integration under `infrastructure/outbound/`.
7.  **Implement Inbound Adapter**: Build the FastAPI HTTP routing and standard payload validation under `infrastructure/inbound/`.
8.  **Setup Composition Root**: Wire the dependencies and config loader under `composition_root/`.
9.  **Write Process Entrypoint**: Setup logging and `asyncio.run(setup())` inside `main.py`.
10. **Build Tests**: Provide a health endpoint test and a simple manual validation script under `tests/`.
