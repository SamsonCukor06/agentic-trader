#!/usr/bin/env bash
# Push a one-line trade-cycle notification to the user's phone via ntfy.sh.
# Replaces the retired email deliverable (Gmail account deleted 2026-07-02).
#
# Usage:  bash ~/.agentic-trader/notify.sh "<message>" [mode]
#   mode = "recap" (default) — end-of-cycle summary, normal priority.
#   mode = "fill"            — a REAL order just filled: high priority, distinct
#                              title/icon/sound so live money stands out from
#                              routine dry-run recaps.
#
# The private topic lives in ~/.agentic-trader/ntfy_topic (or $AGENTIC_NTFY_TOPIC).
# Subscribe to that exact topic in the ntfy app (iOS/Android) to receive pushes.
# Exits 0 quietly if not configured, so the trade cycle never breaks on notify.
set -euo pipefail

MSG="${1:-Agentic trade cycle ran.}"
MODE="${2:-recap}"
TOPIC="${AGENTIC_NTFY_TOPIC:-}"
if [[ -z "$TOPIC" && -f "$HOME/.agentic-trader/ntfy_topic" ]]; then
  TOPIC="$(tr -d '[:space:]' < "$HOME/.agentic-trader/ntfy_topic")"
fi

if [[ -z "$TOPIC" ]]; then
  echo "[notify] no ntfy topic configured — skipping push (report still on disk)."
  exit 0
fi

# Choose header set by mode. A live fill gets urgent priority + a money icon so
# it pushes through even in a phone's low-priority batching.
case "$MODE" in
  fill)
    TITLE="Agentic Trader — LIVE FILL 💰"
    TAGS="money_with_wings,rotating_light"
    PRIORITY="urgent"
    ;;
  *)
    TITLE="Agentic Trader"
    TAGS="chart_with_upwards_trend"
    PRIORITY="default"
    ;;
esac

# Post to ntfy. --fail so a bad HTTP status is visible in logs; but never abort
# the cycle: swallow non-zero so a network blip doesn't fail the whole run.
if curl -fsS \
    -H "Title: ${TITLE}" \
    -H "Tags: ${TAGS}" \
    -H "Priority: ${PRIORITY}" \
    -d "$MSG" \
    "https://ntfy.sh/${TOPIC}" >/dev/null; then
  echo "[notify] pushed (${MODE}) to ntfy topic ${TOPIC}"
else
  echo "[notify] ntfy push (${MODE}) failed (network?) — continuing."
fi
exit 0
