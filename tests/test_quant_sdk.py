from unittest.mock import patch

import pytest

from tradingview_scraper.orchestration.registry import StageRegistry, StageSpec


# Mock Context
class MockContext:
    def __init__(self, run_id, params=None):
        self.run_id = run_id
        self.params = params or {}
        self.raw_pool = []
        self.winners = []
        self.audit_trail = []


# Mock Stage
class MockStage:
    def __init__(self, **kwargs):
        self.params = kwargs

    def execute(self, context):
        context.raw_pool = ["asset1", "asset2"]
        context.audit_trail.append("executed")
        return context


@pytest.fixture
def mock_registry():
    # Reset registry
    StageRegistry._stages = {}
    StageRegistry._specs = {}

    # Register a test stage
    spec = StageSpec(id="selection.ingestion", name="Ingestion", stage_class=MockStage, input_schema={}, output_schema={}, tags=["selection"])
    StageRegistry.register(spec)

    # Mock _ensure_loaded to prevent side effects
    with patch.object(StageRegistry, "_ensure_loaded", return_value=None):
        yield StageRegistry


def test_sdk_run_stage(mock_registry):
    from tradingview_scraper.orchestration.sdk import QuantSDK

    # We pass a mock context explicitly since run_stage doesn't create one by default
    # unless we modify SDK to do so (which might couple it to SelectionContext)
    context = MockContext(run_id="test_run")

    context = QuantSDK.run_stage("selection.ingestion", context=context, params={"candidates_path": "tests/fixtures/candidates.json"})

    assert context.run_id == "test_run"
    assert len(context.raw_pool) > 0
    assert "executed" in context.audit_trail


def test_sdk_run_pipeline(mock_registry):
    # Mocking run_pipeline logic which orchestrates multiple stages
    # For now assuming it runs stages sequentially.
    # We'll just test a single stage pipeline for simplicity or mock the implementation
    pass
