#!/usr/bin/env bash
# One-time, idempotent server preparation for the NavDU (WIUT design) mock-up.
#
# Additive only: it creates its own document root and starts its own container.
# It never touches /opt/navoiyliklar, /opt/udea-static, their Caddy/nginx
# configs, or any running service belonging to those stacks.
#
# Usage (as root on the target server):
#   bash server-setup.sh                # publishes on port 8081
#   WIUT_PORT=9091 bash server-setup.sh # publishes on another port

set -euo pipefail

WIUT_ROOT="${WIUT_ROOT:-/var/www/wuit-navoiyliklar}"
WIUT_PORT="${WIUT_PORT:-8081}"
HERE="$(cd "$(dirname "$0")" && pwd)"

command -v docker >/dev/null || { echo "docker is not installed." >&2; exit 1; }

mkdir -p "$WIUT_ROOT"

# Refuse to steal a port that something else already listens on.
if ss -tlnH "sport = :${WIUT_PORT}" | grep -q . ; then
    if [ "$(docker ps -q -f name='^wiut-static$')" = "" ]; then
        echo "Port ${WIUT_PORT} is already in use by another service. Pick another with WIUT_PORT=." >&2
        exit 1
    fi
fi

cd "$HERE"
WIUT_ROOT="$WIUT_ROOT" WIUT_PORT="$WIUT_PORT" \
    docker compose -p wiut-static up -d

echo
echo "Document root : $WIUT_ROOT"
echo "Published on  : http://$(hostname -I | awk '{print $1}'):${WIUT_PORT}"
