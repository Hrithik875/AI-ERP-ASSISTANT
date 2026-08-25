"""
AI ERP Assistant — Request ID Middleware
=========================================
Generates a UUID X-Request-ID for every incoming request, stores it in a
ContextVar so any code running within the same async task can retrieve it
(e.g. for structured logging), and echoes it in the response headers.

Usage:
    from middleware.request_id import get_request_id
    logger.info(f"[{get_request_id()}] Something happened")
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the current request's correlation ID, or '' if outside a request context."""
    return _request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that:
      1. Reads X-Request-ID from the incoming request headers (if provided by the client).
      2. Generates a fresh UUID v4 if the header is absent.
      3. Stores the ID in a ContextVar so it's accessible throughout the request lifecycle.
      4. Adds X-Request-ID to the response headers.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = _request_id_var.set(request_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _request_id_var.reset(token)
