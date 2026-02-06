import pytest
import threading
import time
from tradingview_scraper.settings import ThreadSafeConfig, TradingViewScraperSettings, set_active_settings, get_settings


def worker_task(profile_name, result_dict):
    # Set context-local settings
    settings = TradingViewScraperSettings(profile=profile_name, top_n=10 if profile_name == "A" else 20)
    token = set_active_settings(settings)

    # Sleep to ensure overlap
    time.sleep(0.1)

    # Verify settings match what we set
    current = get_settings()
    result_dict[profile_name] = current.top_n

    ThreadSafeConfig.reset_active(token)


def test_thread_safe_config_isolation():
    results = {}

    t1 = threading.Thread(target=worker_task, args=("A", results))
    t2 = threading.Thread(target=worker_task, args=("B", results))

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    assert results["A"] == 10
    assert results["B"] == 20
