import json
from pathlib import Path

manifest_path = Path("configs/manifest.json")
if not manifest_path.exists():
    print(f"Manifest not found at {manifest_path.absolute()}")
    exit(1)

with open(manifest_path, "r") as f:
    manifest = json.load(f)

profile_name = "binance_spot_rating_all_long"
profiles = manifest.get("profiles", {})
profile = profiles.get(profile_name)

if profile:
    print(f"Profile {profile_name} FOUND.")
    print(f"Keys: {list(profile.keys())}")
else:
    print(f"Profile {profile_name} NOT FOUND.")
    print(f"Available profiles: {list(profiles.keys())}")
