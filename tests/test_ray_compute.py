from unittest.mock import ANY, MagicMock, patch

import pytest

from tradingview_scraper.orchestration.compute import RayComputeEngine


@pytest.fixture
def mock_ray():
    with patch("tradingview_scraper.orchestration.compute.ray") as mock:
        mock.is_initialized.return_value = False
        yield mock


def test_engine_initialization(mock_ray):
    engine = RayComputeEngine(num_cpus=4)
    engine.ensure_initialized()

    mock_ray.init.assert_called_once_with(num_cpus=4, ignore_reinit_error=True, runtime_env=ANY, _system_config=ANY)


@patch("tradingview_scraper.orchestration.compute.SleeveActor")
def test_dispatch_sleeves(mock_actor_cls, mock_ray):
    mock_actor = MagicMock()
    mock_actor_cls.remote.return_value = mock_actor
    mock_ray.get.return_value = [{"status": "success"}]

    engine = RayComputeEngine()
    sleeves = [{"profile": "p1", "run_id": "r1"}]

    results = engine.execute_sleeves(sleeves)

    mock_actor_cls.remote.assert_called_once()
    mock_actor.run_pipeline.remote.assert_called_once_with("p1", "r1")
    assert results[0]["status"] == "success"


@patch("tradingview_scraper.utils.workspace.WorkspaceManager")
@patch("tradingview_scraper.orchestration.sleeve_executor.get_settings")
def test_sleeve_actor_init(mock_get_settings, mock_workspace_cls):
    from tradingview_scraper.orchestration.sleeve_executor import SleeveActorImpl

    # Mock settings
    mock_s = MagicMock()
    mock_get_settings.return_value = mock_s

    env_vars = {"TV_STRICT_HEALTH": "1"}
    host_cwd = "/host/cwd"

    # Instantiate
    actor = SleeveActorImpl(host_cwd, env_vars)

    # Check WorkspaceManager delegated calls
    mock_workspace_cls.assert_called_once()
    mock_workspace_cls.return_value.setup_worker_workspace.assert_called_once()


@patch("tradingview_scraper.orchestration.compute.execute_stage_remote")
def test_map_stages(mock_execute, mock_ray):
    # Setup
    mock_ray.get.side_effect = lambda futures: futures  # Identity for list
    mock_execute.remote.side_effect = lambda *args: "future_result"

    engine = RayComputeEngine()

    # Mock contexts
    contexts = [MagicMock() for _ in range(3)]

    # Execute
    results = engine.map_stages("test.stage", contexts, params={"p": 1})

    # Verify
    assert len(results) == 3
    assert results[0] == "future_result"
    assert mock_execute.remote.call_count == 3
    # Check arguments of first call
    args = mock_execute.remote.call_args_list[0][0]
    assert args[0] == "test.stage"
    assert args[1] == contexts[0]
    assert args[2] == {"p": 1}


def test_execute_dag(mock_ray):
    with patch.dict("sys.modules", {"prefect_ray": MagicMock()}):
        engine = RayComputeEngine()
        mock_dag = MagicMock()

        engine.execute_dag(mock_dag, params={"run_id": "123"})

    # Verify DAG was run with RayTaskRunner option
    mock_dag.with_options.assert_called_once()
    # The code calls dag.run(), not the context manager's return value
    mock_dag.run.assert_called_with(run_id="123")
