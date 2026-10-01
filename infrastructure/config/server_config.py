import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ServerConfig:
    service_name: str
    host: str
    port: int
    allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "ServerConfig":
        raw_origins = env.get("ALLOWED_ORIGINS", "*")
        return cls(
            service_name=env.get("SERVICE_NAME", "Stepper Microservice"),
            host=env.get("SERVICE_HOST", "127.0.0.1"),
            port=int(env.get("SERVICE_PORT", "8005")),
            allowed_origins=tuple(o.strip() for o in raw_origins.split(",") if o.strip()),
        )
