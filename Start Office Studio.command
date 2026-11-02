#!/bin/sh
# Keep the terminal attached so Ctrl+C stops the local server.
cd -- "$(dirname -- "$0")" || exit 1
export PYTHONDONTWRITEBYTECODE=1
if [ -x ./office-studio-runner ]; then
    ./office-studio-runner "$@"
    office_status=$?
    if [ "$office_status" -ne 0 ]; then
        printf '\nOffice Studio stopped with an error. Press Return to close this window.\n'
        read -r office_answer
    fi
    exit "$office_status"
fi
for office_python in python3 python; do
    if command -v "$office_python" >/dev/null 2>&1 && "$office_python" -B -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        "$office_python" -B ./launch.py "$@"
        office_status=$?
        if [ "$office_status" -ne 0 ]; then
            printf '\nOffice Studio stopped with an error. Press Return to close this window.\n'
            read -r office_answer
        fi
        exit "$office_status"
    fi
done
printf '\nPython 3.10 or newer is required. Install Python 3, then open this launcher again.\nPress Return to close this window.\n'
read -r office_answer
exit 1
