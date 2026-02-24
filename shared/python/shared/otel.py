"""OpenTelemetry bootstrap helpers."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider


def init_otel(service_name: str) -> None:
    """Initialize local tracer provider.

    TODO: add OTLP exporter and FastAPI/Celery instrumentation in production.
    """

    resource = Resource(attributes={SERVICE_NAME: service_name})
    trace.set_tracer_provider(TracerProvider(resource=resource))
