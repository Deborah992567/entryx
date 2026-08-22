#!/usr/bin/env bash
# EntryX Flutter desktop build script — builds for the current platform.
#
# Usage:
#   ./scripts/build_desktop.sh [--release|--debug] [--clean]
#
# Outputs:
#   frontend/build/linux/x64/bundle/   (Linux)
#   frontend/build/macos/Build/Products/  (macOS)
#   frontend/build/windows/x64/runner/    (Windows)

set -euo pipefail

MODE="release"
CLEAN=false

for arg in "$@"; do
  case "$arg" in
    --debug)  MODE="debug" ;;
    --clean)  CLEAN=true ;;
    --release) MODE="release" ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

cd "$(dirname "$0")/../frontend"

if [ "$CLEAN" = true ]; then
  echo "==> Cleaning build artifacts..."
  flutter clean
fi

echo "==> Getting dependencies..."
flutter pub get

echo "==> Analyzing code..."
flutter analyze --no-fatal-infos

echo "==> Running tests..."
flutter test

PLATFORM="$(uname -s)"
case "$PLATFORM" in
  Darwin)
    echo "==> Building macOS desktop ($MODE)..."
    flutter build macos --$MODE
    echo "==> Build complete: frontend/build/macos/Build/Products/"
    ;;
  Linux)
    echo "==> Building Linux desktop ($MODE)..."
    flutter build linux --$MODE
    echo "==> Build complete: frontend/build/linux/x64/bundle/"
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    echo "==> Building Windows desktop ($MODE)..."
    flutter build windows --$MODE
    echo "==> Build complete: frontend/build/windows/x64/runner/"
    ;;
  *)
    echo "Unsupported platform: $PLATFORM"
    exit 1
    ;;
esac

echo "==> Done!"
