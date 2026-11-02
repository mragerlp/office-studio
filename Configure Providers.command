#!/bin/sh
cd -- "$(dirname -- "$0")" || exit 1
exec /bin/sh "./Start Office Studio.command" --configure "$@"
