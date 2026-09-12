import re
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import correlation_id_var

CORRELATION_ID_HEADER = "X-Correlation-ID"

_CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def get_correlation_id() -> str | None:
    return correlation_id_var.get()


def new_correlation_id() -> str:
    return uuid4().hex


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = incoming if incoming and _CORRELATION_ID_PATTERN.match(incoming) else (
            new_correlation_id()
        )
        token = correlation_id_var.set(correlation_id)
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
