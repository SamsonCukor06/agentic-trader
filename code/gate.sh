#!/bin/bash
# Authoritative gate state for the agentic trader — pure, deterministic, NO LLM discretion.
# The trade cycle MUST run this FIRST and use its output VERBATIM for mode/armed/kill/can_place_orders
# everywhere (report header, decisions.jsonl, heartbeat, and the place-vs-paper branch). The cycle must
# NOT infer or recall the mode from memory. If a cycle ever writes "DRY RUN" while this prints LIVE, that
# is a critical failure — this file is the single source of truth.
#
# Usage:  bash ~/.agentic-trader/gate.sh            # prints the gate JSON
#         bash ~/.agentic-trader/gate.sh --heartbeat # ALSO stamps heartbeat.json with mode/armed/kill + now

DIR="$HOME/.agentic-trader"

armed=false; kill=false
[ -f "$DIR/ARMED" ] && armed=true
[ -f "$DIR/KILL" ]  && kill=true

if   [ "$kill"  = true ]; then mode="HALTED"
elif [ "$armed" = true ]; then mode="LIVE"
else                           mode="DRY_RUN"
fi

# US market session in ET (handles EST/EDT automatically via tz database)
et_dow=$(TZ="America/New_York" date +%u)              # 1=Mon .. 7=Sun
et_hm=$(TZ="America/New_York" date +%H%M)             # HHMM
et_date=$(TZ="America/New_York" date +%Y-%m-%d)
hm=$((10#$et_hm))                                     # strip leading zero (avoid octal)
et_now=$(TZ="America/New_York" date "+%Y-%m-%d %H:%M %Z")

# NYSE full-closure holidays (extend annually; verify each new year against nyse.com/markets/hours-calendars)
holidays="2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 2026-06-19 2026-07-03 2026-09-07 2026-11-26 2026-12-25 2027-01-01 2027-01-18 2027-02-15 2027-03-26 2027-05-31 2027-06-18 2027-07-05 2027-09-06 2027-11-25 2027-12-24"
# 13:00 ET early closes
early_closes="2026-11-27 2026-12-24 2027-11-26"

session="closed"
if [ "$et_dow" -le 5 ]; then
  case " $holidays " in *" $et_date "*) session="closed";;
  *)
    close_hm=1600
    case " $early_closes " in *" $et_date "*) close_hm=1300;; esac
    if [ "$hm" -ge 930 ] && [ "$hm" -lt "$close_hm" ]; then session="regular"; fi
  ;;
  esac
fi

# Orders may be placed ONLY when armed, not killed, and in regular hours.
can_trade=false
if [ "$kill" = false ] && [ "$armed" = true ] && [ "$session" = "regular" ]; then
  can_trade=true
fi

armed_file=$([ -f "$DIR/ARMED" ] && echo present || echo absent)

json=$(printf '{"armed":%s,"kill":%s,"mode":"%s","market_session":"%s","can_place_orders":%s,"et_now":"%s","armed_file":"%s"}' \
  "$armed" "$kill" "$mode" "$session" "$can_trade" "$et_now" "$armed_file")

echo "$json"

if [ "$1" = "--heartbeat" ]; then
  now_iso=$(date -u "+%Y-%m-%dT%H:%M:%SZ")
  printf '{"last_cycle":"%s","mode":"%s","armed":%s,"kill":%s,"market_session":"%s"}\n' \
    "$now_iso" "$mode" "$armed" "$kill" "$session" > "$DIR/heartbeat.json"
fi
