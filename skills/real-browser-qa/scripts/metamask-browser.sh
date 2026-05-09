#!/bin/bash
set -euo pipefail

# Launches Playwright's Chromium with MetaMask extension and CDP on port 9222.
# Usage: scripts/metamask-browser.sh [url]
#
# Prerequisites (one-time per machine):
#   1. Chrome installed with MetaMask extension
#   2. METAMASK_PASSWORD env var in ~/.bashrc
#
# The script:
#   - Finds MetaMask extension in the Chrome profile automatically
#   - Copies MetaMask vault data to a persistent testing profile
#   - Ensures Playwright Chromium is installed
#   - Launches Chromium with MetaMask on CDP port 9222

CDP_PORT="${CDP_PORT:-9222}"
TESTING_DIR="$HOME/.metamask-testing"
PROFILE_DIR="$TESTING_DIR/profile"
NODE_DIR="$TESTING_DIR/node"
CHROME_PROFILE="$HOME/Library/Application Support/Google/Chrome/Default"
MM_EXT_ID="nkbihfbeogaeaoehlefnkodbefgpgknn"
URL="${1:-about:blank}"

# Kill any existing process on the CDP port
if lsof -ti:"$CDP_PORT" > /dev/null 2>&1; then
  echo "Stopping existing process on port $CDP_PORT..."
  kill $(lsof -ti:"$CDP_PORT") 2>/dev/null || true
  sleep 1
fi

# Find MetaMask extension directory (latest version)
MM_VERSIONS_DIR="$CHROME_PROFILE/Extensions/$MM_EXT_ID"
if [ ! -d "$MM_VERSIONS_DIR" ]; then
  echo "ERROR: MetaMask extension not found in Chrome profile."
  echo "Install MetaMask in Chrome first."
  exit 1
fi
MM_EXT_PATH="$MM_VERSIONS_DIR/$(ls -1 "$MM_VERSIONS_DIR" | sort -V | tail -1)"
echo "MetaMask extension: $MM_EXT_PATH"

# Ensure Playwright Chromium is installed
CHROMIUM_DIR=$(ls -d "$HOME/Library/Caches/ms-playwright/chromium-"* 2>/dev/null | sort -V | tail -1)
if [ -z "$CHROMIUM_DIR" ]; then
  echo "Installing Playwright Chromium..."
  npx playwright install chromium
  CHROMIUM_DIR=$(ls -d "$HOME/Library/Caches/ms-playwright/chromium-"* 2>/dev/null | sort -V | tail -1)
fi
CHROMIUM_BIN="$CHROMIUM_DIR/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
if [ ! -f "$CHROMIUM_BIN" ]; then
  echo "ERROR: Chromium binary not found at expected path."
  echo "Try: npx playwright install chromium"
  exit 1
fi
echo "Chromium: $CHROMIUM_BIN"

# Ensure testing directories exist
mkdir -p "$PROFILE_DIR/Default"

# Clear session restore data to prevent stale tabs from accumulating
rm -f "$PROFILE_DIR/Default/Last Session" \
      "$PROFILE_DIR/Default/Current Session" \
      "$PROFILE_DIR/Default/Last Tabs" \
      "$PROFILE_DIR/Default/Current Tabs"
rm -rf "$PROFILE_DIR/Default/Sessions"

# Purge ALL MetaMask state in the testing profile before syncing.
# Stale Local Storage, permissions, or session data from previous runs can
# conflict with freshly synced vault data and cause "Cannot read properties
# of undefined" errors inside the extension.
MM_LOCAL_DST="$PROFILE_DIR/Default/Local Extension Settings/$MM_EXT_ID"
MM_IDB_DST="$PROFILE_DIR/Default/IndexedDB/chrome-extension_${MM_EXT_ID}_0.indexeddb.leveldb"

rm -rf "$MM_LOCAL_DST" "$MM_IDB_DST"

# Sync MetaMask vault data from Chrome profile (LevelDB + IndexedDB)
MM_LOCAL_SRC="$CHROME_PROFILE/Local Extension Settings/$MM_EXT_ID"
MM_IDB_SRC="$CHROME_PROFILE/IndexedDB/chrome-extension_${MM_EXT_ID}_0.indexeddb.leveldb"

if [ -d "$MM_LOCAL_SRC" ]; then
  mkdir -p "$MM_LOCAL_DST"
  rsync -a "$MM_LOCAL_SRC/" "$MM_LOCAL_DST/"
  echo "Synced MetaMask Local Extension Settings"
fi

if [ -d "$MM_IDB_SRC" ]; then
  mkdir -p "$MM_IDB_DST"
  rsync -a "$MM_IDB_SRC/" "$MM_IDB_DST/"
  echo "Synced MetaMask IndexedDB"
fi

# Ensure playwright npm package is available for CDP scripts
if [ ! -d "$NODE_DIR/node_modules/playwright" ]; then
  echo "Installing playwright npm package..."
  mkdir -p "$NODE_DIR"
  cd "$NODE_DIR"
  npm init -y > /dev/null 2>&1
  npm install playwright > /dev/null 2>&1
  cd - > /dev/null
fi

# Launch Chromium
echo "Launching Chromium with MetaMask on CDP port $CDP_PORT..."
"$CHROMIUM_BIN" \
  --user-data-dir="$PROFILE_DIR" \
  --disable-extensions-except="$MM_EXT_PATH" \
  --load-extension="$MM_EXT_PATH" \
  --remote-debugging-port="$CDP_PORT" \
  --no-first-run \
  --no-default-browser-check \
  --disable-session-crashed-bubble \
  --noerrdialogs \
  "$URL" &

BROWSER_PID=$!
echo "Browser PID: $BROWSER_PID"

# Wait for CDP to be ready
for i in $(seq 1 15); do
  if curl -s "http://localhost:$CDP_PORT/json/version" > /dev/null 2>&1; then
    echo "CDP ready on port $CDP_PORT"
    echo "Connect with: chromium.connectOverCDP('http://localhost:$CDP_PORT')"
    exit 0
  fi
  sleep 1
done

echo "ERROR: CDP did not become ready within 15 seconds."
kill "$BROWSER_PID" 2>/dev/null || true
exit 1
