#!/bin/sh
set -eu
task_python="${OFFICE_STUDIO_PYTHON:-python3}"
task_repo="$SRCROOT/.."
if ! "$task_python" -c 'import PyInstaller; assert PyInstaller.__version__ == "6.22.3"' >/dev/null 2>&1; then
  echo 'error: Set OFFICE_STUDIO_PYTHON in macos/Local.xcconfig to Python with PyInstaller 6.22.3. See macos/README.md.'
  exit 1
fi
set -- "$task_repo/build_runner.py" build --target macos-arm64 --output "$DERIVED_FILE_DIR/native"
# PyInstaller signs both the bootloader and embedded Python libraries with the same identity.
# Keep its ordinary ad-hoc signature for Debug builds.
if [ "${CODE_SIGNING_ALLOWED:-NO}" = YES ] && [ -n "${EXPANDED_CODE_SIGN_IDENTITY:-}" ] && [ "$EXPANDED_CODE_SIGN_IDENTITY" != "-" ]; then
  set -- "$@" --signing-identity "$EXPANDED_CODE_SIGN_IDENTITY"
fi
"$task_python" -B "$@"
task_destination="$TARGET_BUILD_DIR/$CONTENTS_FOLDER_PATH/Helpers"
mkdir -p "$task_destination"
/usr/bin/install -m 755 "$DERIVED_FILE_DIR/native/office-studio-runner" "$task_destination/office-studio-runner"
