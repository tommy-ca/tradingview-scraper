import logging
from opentelemetry import trace


class TelemetryLogRecord(logging.LogRecord):
    """Custom LogRecord that injects trace and span IDs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            ctx = span.get_span_context()
            self.trace_id = format(ctx.trace_id, "032x")
            self.span_id = format(ctx.span_id, "016x")
        else:
            self.trace_id = "0" * 32
            self.span_id = "0" * 16


def get_telemetry_logger(name: str) -> logging.Logger:
    """Returns a logger configured with the TelemetryLogRecord factory."""
    logging.setLogRecordFactory(TelemetryLogRecord)
    logger = logging.getLogger(name)

    # Standard format with trace/span IDs
    fmt = "%(asctime)s %(levelname)s [%(trace_id)s|%(span_id)s] %(name)s: %(message)s"

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
