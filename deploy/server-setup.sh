#!/usr/bin/env bash
# One-time, idempotent server preparation for the NDU site (NavDU, WIUT design).
#
# Additive only: it creates its own document root and starts its own container.
# It never touches /opt/navoiyliklar, /opt/udea-static, /opt/wiut-static,
# /opt/newuu-static, their Caddy/nginx configs, or any running service
# belonging to those stacks.
#
# Usage (as root on the target server):
#   bash server-setup.sh               # publishes on port 8083
#   NDU_PORT=9093 bash server-setup.sh # publishes on another port

set -euo pipefail

NDU_ROOT="${NDU_ROOT:-/var/www/ndu}"
NDU_PORT="${NDU_PORT:-8083}"
HERE="$(cd "$(dirname "$0")" && pwd)"

command -v docker >/dev/null || { echo "docker is not installed." >&2; exit 1; }

mkdir -p "$NDU_ROOT"

# Refuse to steal a port that something else already listens on.
if ss -tlnH "sport = :${NDU_PORT}" | grep -q . ; then
    if [ "$(docker ps -q -f name='^ndu-static$')" = "" ]; then
        echo "Port ${NDU_PORT} is already in use by another service. Pick another with NDU_PORT=." >&2
        exit 1
    fi
fi

cd "$HERE"
NDU_ROOT="$NDU_ROOT" NDU_PORT="$NDU_PORT" \
    docker compose -p ndu-static up -d

echo
echo "Document root : $NDU_ROOT"
echo "Published on  : http://$(hostname -I | awk '{print $1}'):${NDU_PORT}"
