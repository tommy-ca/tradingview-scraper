import pytest
import threading
import time
from tradingview_scraper.settings import ThreadSafeConfig, TradingViewScraperSettings, set_active_settings, get_settings


def worker_task(profile_name, result_dict):
    # Set context-local settings
    settings = TradingViewScraperSettings(profile=profile_name, top_n=10 if profile_name == "A" else 20)
    token = set_active_settings(settings)

    # Sleep to ensure overlap between threads
    time.sleep(0.5)

    # Verify settings match what we set in this context
    current = get_settings()
    result_dict[profile_name] = current.top_n
    result_dict[profile_name + "_profile"] = current.profile

    ThreadSafeConfig.reset_active(token)


def test_thread_safe_config_isolation():
    """
    Verifies that ThreadSafeConfig correctly isolates settings across threads.
    Thread B starting and changing settings should not affect Thread A's context.
    """
    results = {}

    t1 = threading.Thread(target=worker_task, args=("A", results))
    t2 = threading.Thread(target=worker_task, args=("B", results))

    t1.start()
    time.sleep(0.1)  # Ensure T1 starts first
    t2.start()

    t1.join()
    t2.join()

    # Thread A should have its own settings preserved
    assert results["A"] == 10
    assert results["A_profile"] == "A"

    # Thread B should have its own settings preserved
    assert results["B"] == 20
    assert results["B_profile"] == "B"


if __name__ == "__main__":
    pytest.main([__file__])
