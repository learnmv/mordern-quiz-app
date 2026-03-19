"""OpenTelemetry tracing configuration for distributed tracing."""
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)

# Global tracer provider
_tracer_provider: Optional[TracerProvider] = None


def setup_tracing(
    service_name: str = "quiz-app-api",
    service_version: str = "1.0.0",
    exporter_endpoint: Optional[str] = None,
    console_export: bool = False
) -> TracerProvider:
    """Setup OpenTelemetry tracing.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        exporter_endpoint: OTLP endpoint URL (e.g., http://jaeger:4317)
        console_export: Also export to console for debugging

    Returns:
        Configured TracerProvider
    """
    global _tracer_provider

    # Create resource
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
    })

    # Create tracer provider
    _tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(_tracer_provider)

    # Add OTLP exporter if endpoint provided
    if exporter_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            otlp_exporter = OTLPSpanExporter(
                endpoint=exporter_endpoint,
                insecure=True  # Use TLS in production
            )
            span_processor = BatchSpanProcessor(otlp_exporter)
            _tracer_provider.add_span_processor(span_processor)
            logger.info(f"OTLP exporter configured: {exporter_endpoint}")
        except Exception as e:
            logger.error(f"Failed to configure OTLP exporter: {e}")

    # Add console exporter for debugging
    if console_export:
        console_exporter = ConsoleSpanExporter()
        span_processor = BatchSpanProcessor(console_exporter)
        _tracer_provider.add_span_processor(span_processor)
        logger.info("Console span exporter configured")

    return _tracer_provider


def get_tracer(name: str = "app"):
    """Get a tracer instance.

    Args:
        name: Tracer name

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


def instrument_fastapi(app):
    """Instrument FastAPI application.

    Args:
        app: FastAPI application instance
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")


def instrument_sqlalchemy():
    """Instrument SQLAlchemy for database tracing."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument()
        logger.info("SQLAlchemy instrumented")
    except Exception as e:
        logger.error(f"Failed to instrument SQLAlchemy: {e}")


def instrument_httpx():
    """Instrument HTTPX for HTTP client tracing."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumented")
    except Exception as e:
        logger.error(f"Failed to instrument HTTPX: {e}")


def instrument_all(app):
    """Instrument all supported libraries.

    Args:
        app: FastAPI application instance
    """
    instrument_fastapi(app)
    instrument_sqlalchemy()
    instrument_httpx()


class TracingContext:
    """Context manager for manual span creation."""

    def __init__(self, span_name: str, attributes: Optional[dict] = None):
        self.span_name = span_name
        self.attributes = attributes or {}
        self.span = None

    def __enter__(self):
        tracer = get_tracer()
        self.span = tracer.start_span(self.span_name)
        for key, value in self.attributes.items():
            self.span.set_attribute(key, value)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.span.record_exception(exc_val)
        self.span.end()


def get_current_span():
    """Get the current active span."""
    return trace.get_current_span()


def add_span_attribute(key: str, value):
    """Add attribute to current span.

    Args:
        key: Attribute key
        value: Attribute value
    """
    span = get_current_span()
    if span:
        span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[dict] = None):
    """Add event to current span.

    Args:
        name: Event name
        attributes: Event attributes
    """
    span = get_current_span()
    if span:
        span.add_event(name, attributes)
