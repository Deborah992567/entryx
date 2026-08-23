#!/usr/bin/env bash
# Package EntryX macOS app into a .dmg installer.
#
# Prerequisites:
#   - Flutter desktop build completed (build_desktop.sh)
#   - create-dmg installed (brew install create-dmg)
#
# Usage: ./scripts/package_macos.sh

set -euo pipefail

cd "$(dirname "$0")/.."
APP_NAME="EntryX"
BUILD_DIR="frontend/build/macos/Build/Products"
DMG_NAME="EntryX-macos.dmg"
APP_PATH="$BUILD_DIR/Release/$APP_NAME.app"

if [ ! -d "$APP_PATH" ]; then
  echo "ERROR: $APP_PATH not found. Run build_desktop.sh first."
  exit 1
fi

echo "==> Creating DMG..."
mkdir -p dist

create-dmg \
  --volname "$APP_NAME" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon "$APP_NAME.app" 175 190 \
  --app-drop-link 425 190 \
  "dist/$DMG_NAME" \
  "$APP_PATH" \
  || {
    echo "create-dmg failed, falling back to hdiutil..."
    mkdir -p /tmp/dmg-staging
    cp -R "$APP_PATH" /tmp/dmg-staging/
    ln -s /Applications /tmp/dmg-staging/Applications
    hdiutil create -volname "$APP_NAME" -srcfolder /tmp/dmg-staging -ov -format UDZO "dist/$DMG_NAME"
    rm -rf /tmp/dmg-staging
  }

echo "==> DMG created: dist/$DMG_NAME"
echo "==> Done!"
