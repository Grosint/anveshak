#!/usr/bin/env bash
# scripts/check_env.sh — Pre-flight env var check for make up
#
# Parses compose file(s) for ${VAR} references WITHOUT defaults (no :- syntax).
# These are truly required — compose silently injects empty strings if missing.
# Vars with defaults (${VAR:-default}) are safe to omit.
#
# Usage: scripts/check_env.sh compose_file [compose_file ...]

set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Usage: $0 compose_file [compose_file ...]"
  exit 1
fi

COMPOSE_FILES="$@"

# Extract ${VAR} patterns WITHOUT defaults (no :- or :+ syntax)
# Match ${UPPER_CASE} but NOT ${UPPER_CASE:-...} or ${UPPER_CASE:+...}
REQUIRED_VARS=$(grep -hoE '\$\{[A-Z_]+\}' $COMPOSE_FILES 2>/dev/null | \
  sed 's/[${}]//g' | sort -u || true)

if [ -z "$REQUIRED_VARS" ]; then
  exit 0
fi

# Source .env to get current values
set -a
# shellcheck disable=SC1091
source .env 2>/dev/null || true
set +a

MISSING=()

for var in $REQUIRED_VARS; do
  if [ -z "${!var:-}" ]; then
    MISSING+=("$var")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  printf "\n  \033[1;31mERROR: Required env vars missing or empty in .env:\033[0m\n\n"
  for var in "${MISSING[@]}"; do
    printf "    - %s\n" "$var"
  done
  printf "\n  Fill these in .env before running make up.\n"
  printf "  See .env.example for descriptions and defaults.\n\n"
  exit 1
fi
