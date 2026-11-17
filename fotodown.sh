#!/usr/bin/env bash
# FotoDown Compatibility Wrapper (renamed to Vitrina)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/vitrina.sh" "$@"
