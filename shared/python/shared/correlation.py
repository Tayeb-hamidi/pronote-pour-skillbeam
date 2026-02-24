"""Correlation-id context and FastAPI middleware."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Read current correlation id from context var."""

    return correlation_id_var.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach or generate correlation id for each request."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        corr_id = request.headers.get("x-correlation-id", str(uuid4()))
        token = correlation_id_var.set(corr_id)
        try:
            response = await call_next(request)
            response.headers["x-correlation-id"] = corr_id
            return response
        finally:
            correlation_id_var.reset(token)
