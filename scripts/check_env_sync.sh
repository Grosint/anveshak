#!/usr/bin/env bash
# =============================================================================
# Anveshak — .env / .env.example Drift Detector
#
# Compares active (non-commented) keys between .env and .env.example.
# Reports missing keys that will silently default to empty/false.
#
# Usage:
#   ./scripts/check_env_sync.sh     # from project root
#   make check-env-sync             # via Makefile
#
# Exit codes:
#   0 — all keys match
#   1 — drift detected (missing keys in .env)
# =============================================================================

set -uo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ENV_FILE=".env"
EXAMPLE_FILE=".env.example"
ERRORS=0
WARNINGS=0

# ---------------------------------------------------------------------------
# Pre-checks
# ---------------------------------------------------------------------------

if [ ! -f "$EXAMPLE_FILE" ]; then
    printf "${RED}ERROR:${NC} %s not found — run from project root\n" "$EXAMPLE_FILE"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    printf "${RED}ERROR:${NC} %s not found — run: cp .env.example .env\n" "$ENV_FILE"
    exit 1
fi

# ---------------------------------------------------------------------------
# Extract active keys (non-commented KEY=value lines)
# ---------------------------------------------------------------------------

extract_keys() {
    sed -n 's/^\([A-Z_][A-Z_0-9]*\)=.*/\1/p' "$1" | sort -u
}

EXAMPLE_KEYS=$(extract_keys "$EXAMPLE_FILE")
ENV_KEYS=$(extract_keys "$ENV_FILE")

EXAMPLE_COUNT=$(echo "$EXAMPLE_KEYS" | wc -l | tr -d ' ')
ENV_COUNT=$(echo "$ENV_KEYS" | wc -l | tr -d ' ')

printf "${BOLD}${CYAN}━━━ .env Drift Check ━━━${NC}\n"
printf "  .env.example: %s keys\n" "$EXAMPLE_COUNT"
printf "  .env:         %s keys\n\n" "$ENV_COUNT"

# ---------------------------------------------------------------------------
# Keys in .env.example missing from .env (ERROR — will silently default)
# ---------------------------------------------------------------------------

MISSING_FROM_ENV=$(comm -23 <(echo "$EXAMPLE_KEYS") <(echo "$ENV_KEYS"))

if [ -n "$MISSING_FROM_ENV" ]; then
    printf "${RED}${BOLD}ERRORS — keys in .env.example missing from .env:${NC}\n"
    printf "${RED}  These will silently default to empty/false — features may be disabled!${NC}\n"
    while IFS= read -r key; do
        printf "${RED}  ✗ %s${NC}\n" "$key"
        ERRORS=$((ERRORS + 1))
    done <<< "$MISSING_FROM_ENV"
    echo ""
fi

# ---------------------------------------------------------------------------
# Keys in .env missing from .env.example (WARNING — undocumented)
# ---------------------------------------------------------------------------

MISSING_FROM_EXAMPLE=$(comm -13 <(echo "$EXAMPLE_KEYS") <(echo "$ENV_KEYS"))

if [ -n "$MISSING_FROM_EXAMPLE" ]; then
    printf "${YELLOW}${BOLD}WARNINGS — keys in .env not in .env.example:${NC}\n"
    printf "${YELLOW}  These are undocumented — add to .env.example or remove from .env${NC}\n"
    while IFS= read -r key; do
        printf "${YELLOW}  ⚠ %s${NC}\n" "$key"
        WARNINGS=$((WARNINGS + 1))
    done <<< "$MISSING_FROM_EXAMPLE"
    echo ""
fi

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    printf "${GREEN}${BOLD}  ✓ .env and .env.example are in sync (%s keys)${NC}\n" "$EXAMPLE_COUNT"
    exit 0
elif [ "$ERRORS" -eq 0 ]; then
    printf "${YELLOW}${BOLD}  ⚠ %d warning(s), 0 errors — .env has undocumented keys${NC}\n" "$WARNINGS"
    exit 0
else
    printf "${RED}${BOLD}  ✗ %d error(s), %d warning(s) — .env is missing keys from .env.example${NC}\n" "$ERRORS" "$WARNINGS"
    printf "  Run: ${CYAN}diff <(grep '^[A-Z]' .env.example | cut -d= -f1 | sort) <(grep '^[A-Z]' .env | cut -d= -f1 | sort)${NC}\n"
    exit 1
fi
