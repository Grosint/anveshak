#!/usr/bin/env bash
# Container healthcheck for ARQ workers and scheduler loops, based on the
# process's own heartbeat.
#
# Usage (from a compose healthcheck):
#   test: ["CMD", "bash", "/workspace/sdk/arq_health.sh", "arq:scraper"]
#   test: ["CMD", "bash", "/workspace/sdk/arq_health.sh", "anveshak:scheduler:scrape-web"]
#
# The argument is a key prefix; ":health-check" is appended. ARQ writes that key
# for a worker, and sdk/anveshak/heartbeat.py writes it for the two schedulers,
# which are plain asyncio loops rather than ARQ workers.
#
# Why not `kill -0 1`:
#   A wedged ARQ worker looks identical to a busy one. When blocking work runs on
#   the event loop the whole loop freezes, `job_timeout` cannot fire because
#   asyncio.wait_for needs the loop to tick, and PID 1 is very much alive. An
#   analyst worker once reported healthy for 40 minutes at 900% CPU while making
#   no progress.
#
# Why not `python -c 'import anveshak.<svc>.jobs'`:
#   That imports the whole job graph, dragging in crawl4ai, torch and spaCy. It
#   measured 17.9s against a 10s timeout on a worker at its cpus: cap, so the
#   container flapped to unhealthy purely from the cost of its own probe. It also
#   proves nothing about the running worker, since it exercises a fresh process.
#
# Why not a Python script that just talks to Redis:
#   `docker exec` is scheduled inside the container's own CPU quota, so on a
#   saturated worker even a bare interpreter start is slow. Measured on the web
#   scraper at its cap: `python -m ...` took 15.9s, this script took 1.2s, and
#   most of that 1.2s is docker exec overhead rather than the probe. A probe whose
#   job is to stay reliable under load must not need an interpreter.
#
# How it works:
#   ARQ writes its health key with psetex(key, (health_check_interval + 1) * 1000),
#   so the key exists only if the worker's event loop ticked within the last
#   health_check_interval seconds. Presence of the key is the liveness signal and a
#   frozen loop cannot fake it, so no timestamp parsing is needed. Every
#   WorkerSettings in this repo sets health_check_interval = 30; ARQ's own default
#   is 3600, which would take an hour to notice a dead worker.
#   The schedulers do the same thing with psetex directly, on HEARTBEAT_TTL_S,
#   refreshed while they sleep between cycles rather than once per cycle.
#
# Exit codes: 0 healthy, 1 unhealthy, 2 usage error.

set -uo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 <key-prefix>   e.g. $0 arq:scraper, $0 anveshak:scheduler:scrape-web" >&2
    exit 2
fi

key_prefix="$1"
key="${key_prefix}:health-check"

# Parse host and port out of REDIS_URL (redis://host:port/db). Falls back to the
# compose service name, which is what every service uses today.
url="${REDIS_URL:-redis://redis:6379/0}"
hostport="${url#*://}"     # strip scheme
hostport="${hostport%%/*}" # strip /db
hostport="${hostport##*@}" # strip any user:pass@
host="${hostport%%:*}"
port="${hostport##*:}"
[[ "$port" == "$host" ]] && port=6379

# The brace group scopes the 2>/dev/null to the redirect. Written as
# `exec 3<>... 2>/dev/null` it would apply to the shell instead, since exec with
# no command redirects the current shell, and every later error message would go
# to /dev/null. bash prints its own resolver noise here; ours is the useful one.
if ! { exec 3<>"/dev/tcp/${host}/${port}"; } 2>/dev/null; then
    echo "cannot open a socket to redis at ${host}:${port}" >&2
    exit 1
fi

# Redis accepts inline commands, so no RESP encoding is needed for EXISTS.
printf 'EXISTS %s\r\n' "$key" >&3

if ! read -r -t 5 reply <&3; then
    echo "no reply from redis at ${host}:${port} within 5s" >&2
    exec 3<&-
    exit 1
fi
exec 3<&-

# Integer reply, ":1" for present and ":0" for absent. Strip the trailing CR.
reply="${reply%$'\r'}"

if [[ "$reply" == ":1" ]]; then
    exit 0
fi

if [[ "$reply" == ":0" ]]; then
    echo "${key} is absent: the process has not recorded health within its heartbeat TTL. It is dead or its event loop is blocked." >&2
    exit 1
fi

echo "unexpected reply from redis for EXISTS ${key}: ${reply}" >&2
exit 1
