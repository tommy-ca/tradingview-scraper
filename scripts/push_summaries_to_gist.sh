#!/bin/bash
set -e

# Configuration
SUMMARY_DIR="summaries"
GIST_ID="${GIST_ID:-e888e1eab0b86447c90c26e92ec4dc36}"
TEMP_DIR=".temp_gist_$(date +%s)"

if [ -z "$GIST_ID" ]; then
    echo "Error: GIST_ID not set. Please provide it as an environment variable."
    exit 1
fi

echo "🚀 Syncing summaries to Gist: $GIST_ID"

# 1. Clone the gist repository
git clone "https://gist.github.com/$GIST_ID.git" "$TEMP_DIR"

# 2. Sync files from summaries/ to the temp dir
# This ensures deletions are handled correctly
rsync -av --delete --exclude='.git' "$SUMMARY_DIR/" "$TEMP_DIR/"

# 3. Commit and push
cd "$TEMP_DIR"
git add -A
if git diff --staged --quiet; then
    echo "✅ No changes to push."
else
    git commit -m "update portfolio summaries - $(date +'%Y-%m-%d %H:%M:%S')"
    git push
    echo "✅ Successfully updated Gist."
fi

# 4. Cleanup
cd ..
rm -rf "$TEMP_DIR"
