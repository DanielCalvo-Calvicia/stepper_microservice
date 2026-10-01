from collections.abc import AsyncGenerator
from typing import Any

from fastapi import status
from fastapi.responses import Response


class RequestBodySafeStreamingResponse(Response):
    """Stream response bytes without concurrently reading the ASGI receive channel.

    Starlette's StreamingResponse listens for disconnects by calling receive() while response
    chunks are produced. The command stream endpoint also consumes request.stream() while the
    response is produced, so a second receive() consumer can race the request body.
    """

    def __init__(
        self,
        content: AsyncGenerator[str, None],
        media_type: str,
        headers: dict[str, str] | None = None,
        status_code: int = status.HTTP_200_OK,
    ) -> None:
        super().__init__(
            content=None, status_code=status_code, headers=headers, media_type=media_type
        )
        self.body_iterator = content
        self.raw_headers = [
            (name, value) for name, value in self.raw_headers if name.lower() != b"content-length"
        ]

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:  # noqa: ANN401
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        async for chunk in self.body_iterator:
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk.encode(self.charset),
                    "more_body": True,
                }
            )
        await send({"type": "http.response.body", "body": b"", "more_body": False})
