import functools
from typing import Optional
from opentelemetry import trace
from tradingview_scraper.telemetry.provider import TelemetryProvider


def get_tracer():
    provider = TelemetryProvider()
    if not provider.is_initialized:
        provider.initialize()
    return provider.tracer


def trace_span(name: str, attributes: Optional[dict] = None):
    """Decorator to wrap a function in an OpenTelemetry span."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
                return func(*args, **kwargs)

        return wrapper

    return decorator
