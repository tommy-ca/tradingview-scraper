import os
from tradingview_scraper.settings import get_settings

print(f"Env TV_EXPORT_RUN_ID: {os.environ.get('TV_EXPORT_RUN_ID')}")
print(f"Settings Run ID: {get_settings().run_id}")
