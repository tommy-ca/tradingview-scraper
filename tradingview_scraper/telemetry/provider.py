import threading

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


class TelemetryProvider:
    """
    Singleton manager for OpenTelemetry initialization and access.
    Supports console and OTLP exporters.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TelemetryProvider, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def initialize(self, service_name: str = "quant-platform", console_export: bool = False):
        if self._initialized:
            return

        resource = Resource.create({"service.name": service_name})

        # 1. Tracing Setup
        tracer_provider = TracerProvider(resource=resource)
        if console_export:
            tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(tracer_provider)
        self.tracer = trace.get_tracer(__name__)

        # 2. Metrics Setup
        metric_readers = []
        if console_export:
            metric_readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))

        meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
        metrics.set_meter_provider(meter_provider)
        self.meter = metrics.get_meter(__name__)

        self._initialized = True

    @property
    def is_initialized(self) -> bool:
        return self._initialized
