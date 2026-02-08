import pytest


# Mock BasePipelineStage for testing purposes
class MockStage:
    def __init__(self, **kwargs):
        self.params = kwargs

    def execute(self, context):
        return context


def test_stage_registration():
    from tradingview_scraper.orchestration.registry import StageRegistry, StageSpec

    # Clear registry for test isolation if needed, though mostly fresh per test in pytest
    # But since it's a class variable, we might want to be careful.
    # For now assuming clean state or we can reset it.
    StageRegistry._stages = {}

    spec = StageSpec(id="test.stage", name="Test Stage", stage_class=MockStage, input_schema={"type": "object"}, output_schema={"type": "object"}, tags=["test"])

    StageRegistry.register(spec)
    assert StageRegistry.get("test.stage") == spec


def test_stage_list_by_tag():
    from unittest.mock import patch

    from tradingview_scraper.orchestration.registry import StageRegistry, StageSpec

    # Reset registry state
    StageRegistry._stages = {}
    StageRegistry._specs = {}

    # Mock _ensure_loaded to prevent side effects from loading real stages
    with patch.object(StageRegistry, "_ensure_loaded", return_value=None):
        spec1 = StageSpec(id="test.stage1", name="Test Stage 1", stage_class=MockStage, input_schema={}, output_schema={}, tags=["selection", "test"])
        spec2 = StageSpec(id="test.stage2", name="Test Stage 2", stage_class=MockStage, input_schema={}, output_schema={}, tags=["risk"])

        StageRegistry.register(spec1)
        StageRegistry.register(spec2)

        selection_stages = StageRegistry.list_stages(tag="selection")
        assert len(selection_stages) == 1
        assert selection_stages[0].id == "test.stage1"

        all_stages = StageRegistry.list_stages()
        assert len(all_stages) == 2


def test_unknown_stage_raises():
    from tradingview_scraper.orchestration.registry import StageRegistry

    with pytest.raises(KeyError):
        StageRegistry.get("nonexistent.stage")


def test_decorator_registration():
    from tradingview_scraper.orchestration.registry import StageRegistry, StageSpec

    StageRegistry._stages = {}

    # Create the spec first
    spec = StageSpec(
        id="decorated.stage",
        name="Decorated Stage",
        stage_class=None,  # Will be set by register
        input_schema={},
        output_schema={},
        tags=["decorated"],
    )

    # Use the decorator
    @StageRegistry.register_class(spec)
    class DecoratedStage(MockStage):
        pass

    retrieved_spec = StageRegistry.get("decorated.stage")
    assert retrieved_spec.id == "decorated.stage"
    assert retrieved_spec.stage_class == DecoratedStage
