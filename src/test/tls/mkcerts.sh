#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/cert.pem" ] && [ -f "$SCRIPT_DIR/key.pem" ]; then
    # Certificate and key already exist. Skipping generation.
    exit 0
fi

openssl req -x509 -newkey rsa:4096 -keyout "$SCRIPT_DIR/key.pem" -out "$SCRIPT_DIR/cert.pem" -days 365 -nodes -subj "/CN=localhost"
