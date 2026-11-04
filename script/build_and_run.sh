#!/bin/sh
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
task_mode="${1:-run}"
task_build="$task_root/macos/DerivedData"
case "$task_mode" in run|--verify) ;; *) echo "Usage: $0 [--verify]" >&2; exit 2 ;; esac
xcodebuild -project "$task_root/macos/OfficeStudio.xcodeproj" -scheme OfficeStudio \
  -configuration Debug -derivedDataPath "$task_build" build
task_app="$task_build/Build/Products/Debug/Office Studio.app"
if [ "$task_mode" = --verify ]; then
  python3 -B "$task_root/macos/tests/test_app.py" "$task_app"
else
  /usr/bin/open "$task_app"
fi
