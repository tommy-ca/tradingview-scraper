from pathlib import Path

manifest_path = Path("configs/manifest.json")
lines = manifest_path.read_text().splitlines(keepends=True)

# Lines to keep: 1-707 (indices 0-706)
# Lines to skip: 708-772 (indices 707-771)
# Lines to keep: 773-end (indices 772-end)

# Verify the content at the boundaries to be absolutely sure
print(f"Line 707 (kept): {lines[706].strip()}")
print(f"Line 708 (skipped): {lines[707].strip()}")
print(f"Line 772 (skipped): {lines[771].strip()}")
print(f"Line 773 (kept): {lines[772].strip()}")

if lines[706].strip() == "}," and lines[707].strip().startswith('"data":') and lines[771].strip() == "}," and lines[772].strip().startswith('"meta_binance_trend":'):
    new_lines = lines[:707] + lines[772:]
    manifest_path.write_text("".join(new_lines))
    print("Manifest patched successfully.")
else:
    print("Verification failed. Aborting patch.")
    exit(1)
