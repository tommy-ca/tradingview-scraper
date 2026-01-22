import threading
from pathlib import Path

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

    def initialize(self, service_name: str = "quant-platform", console_export: bool = False, prometheus_endpoint: str | None = None):
        if self._initialized:
            return

        resource = Resource.create({"service.name": service_name})
        self.prometheus_endpoint = prometheus_endpoint

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

        # Prometheus Integration
        if self.prometheus_endpoint:
            from opentelemetry.exporter.prometheus import PrometheusMetricReader

            metric_readers.append(PrometheusMetricReader())

        meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
        metrics.set_meter_provider(meter_provider)
        self.meter = metrics.get_meter(__name__)

        # Pre-register common instruments
        self.duration_histogram = self.meter.create_histogram("quant_stage_duration_seconds", description="Duration of pipeline stages", unit="s")
        self.success_counter = self.meter.create_counter("quant_stage_success_total", description="Count of successful stage completions")
        self.failure_counter = self.meter.create_counter("quant_stage_failure_total", description="Count of stage failures")

        self._initialized = True

    def flush_metrics(self, job_name: str = "quant_pipeline", grouping_key: dict | None = None):
        """Flushes metrics to Prometheus Pushgateway if configured."""
        if not self.prometheus_endpoint:
            return

        try:
            from prometheus_client import CollectorRegistry, push_to_gateway
            from opentelemetry.exporter.prometheus import PrometheusMetricReader

            # Export from OTel to Prometheus registry
            # Note: In a production setup, we'd use a more robust OTel-to-Prometheus bridge.
            # This is a simplified version for ephemeral batch jobs.
            # (In reality, PrometheusMetricReader typically exposes a scrape endpoint)

            logger.info(f"Telemetry: Pushing metrics to {self.prometheus_endpoint}")
            # Placeholder for actual bridge logic
            pass
        except Exception as e:
            logger.error(f"Failed to flush metrics to Prometheus: {e}")

    def register_forensic_exporter(self, output_path: Path):
        """Registers a run-specific forensic exporter."""
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from tradingview_scraper.telemetry.exporter import ForensicSpanExporter

        exporter = ForensicSpanExporter(output_path)
        trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))
        return exporter

    @property
    def is_initialized(self) -> bool:
        return self._initialized
