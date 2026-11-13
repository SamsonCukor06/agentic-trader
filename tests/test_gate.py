"""Tests for code/gate.sh, the deterministic safety gate.

gate.sh decides whether the agent may place real orders. It reads two flag files
(ARMED and KILL) in $HOME/.agentic-trader and the current US Eastern time, then
prints one line of JSON that the agent must copy exactly.

Each test runs the real script with:
  * HOME set to a temporary folder, so the live ~/.agentic-trader is never read or written;
  * a stand-in `date` command first on PATH that pins "now" to a chosen moment.
"""
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

GATE = Path(__file__).resolve().parent.parent / "code" / "gate.sh"
ET = ZoneInfo("America/New_York")
UTC = timezone.utc

OUTPUT_KEYS = {"armed", "kill", "mode", "market_session", "can_place_orders", "et_now", "armed_file"}


def et(year, month, day, hour, minute):
    """A moment in US Eastern time (EST or EDT, whichever applies that day)."""
    return datetime(year, month, day, hour, minute, tzinfo=ET)


# A normal trading day (Wednesday Nov 4, 2026) in the middle of the session.
TRADING_DAY_10AM = et(2026, 11, 4, 10, 0)


def _fake_date_script():
    """A `date` that behaves like the real one but always reports $FAKE_EPOCH as now."""
    real = shutil.which("date")
    probe = subprocess.run([real, "--version"], capture_output=True, text=True)
    if probe.returncode == 0 and "GNU" in probe.stdout:  # Linux (GitHub's Ubuntu runner)
        pin = f'exec "{real}" -d "@$FAKE_EPOCH" "$@"'
    else:  # macOS / BSD date
        pin = f'exec "{real}" -r "$FAKE_EPOCH" "$@"'
    return f"#!/bin/bash\n{pin}\n"


@pytest.fixture
def state_dir(tmp_path):
    """The temporary stand-in for ~/.agentic-trader."""
    d = tmp_path / "home" / ".agentic-trader"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def run_gate(tmp_path, state_dir):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shim = bindir / "date"
    shim.write_text(_fake_date_script())
    shim.chmod(0o755)

    def run(at, armed=False, kill=False, heartbeat=False):
        for name, present in (("ARMED", armed), ("KILL", kill)):
            flag = state_dir / name
            if present:
                flag.touch()
            elif flag.exists():
                flag.unlink()
        env = dict(
            os.environ,
            HOME=str(state_dir.parent),
            PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}",
            FAKE_EPOCH=str(int(at.timestamp())),
        )
        args = ["bash", str(GATE)] + (["--heartbeat"] if heartbeat else [])
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 1, f"expected one JSON line, got: {result.stdout!r}"
        return json.loads(lines[0])

    return run


# --- Mode and permission to trade -------------------------------------------------

@pytest.mark.parametrize(
    "armed, kill, mode, can_trade",
    [
        (False, False, "DRY_RUN", False),
        (True, False, "LIVE", True),
        (True, True, "HALTED", False),   # the kill switch beats ARMED
        (False, True, "HALTED", False),
    ],
    ids=["no-flags", "armed", "armed+kill", "kill-only"],
)
def test_mode_and_permission_follow_flag_files(run_gate, armed, kill, mode, can_trade):
    out = run_gate(TRADING_DAY_10AM, armed=armed, kill=kill)
    assert out["mode"] == mode
    assert out["armed"] is armed
    assert out["kill"] is kill
    assert out["market_session"] == "regular"
    assert out["can_place_orders"] is can_trade


def test_output_has_exactly_the_documented_fields(run_gate):
    assert set(run_gate(TRADING_DAY_10AM)) == OUTPUT_KEYS


def test_armed_file_field_reports_whether_the_file_exists(run_gate):
    assert run_gate(TRADING_DAY_10AM, armed=True)["armed_file"] == "present"
    assert run_gate(TRADING_DAY_10AM, armed=False)["armed_file"] == "absent"


def test_armed_outside_market_hours_is_live_but_cannot_place_orders(run_gate):
    saturday = et(2026, 11, 7, 12, 0)
    out = run_gate(saturday, armed=True)
    assert out["mode"] == "LIVE"
    assert out["market_session"] == "closed"
    assert out["can_place_orders"] is False


# --- Market session: bells, weekends, holidays, early closes ---------------------

@pytest.mark.parametrize(
    "when, session",
    [
        (et(2026, 11, 4, 9, 29), "closed"),     # one minute before the open
        (et(2026, 11, 4, 9, 30), "regular"),    # opening bell
        (et(2026, 11, 4, 15, 59), "regular"),   # last minute of the session
        (et(2026, 11, 4, 16, 0), "closed"),     # closing bell
        (et(2026, 11, 4, 0, 5), "closed"),      # just after midnight
        (et(2026, 11, 4, 8, 9), "closed"),      # "0809" is not valid octal; the script must not choke on it
        (et(2026, 11, 7, 12, 0), "closed"),     # Saturday
        (et(2026, 11, 8, 12, 0), "closed"),     # Sunday
        (et(2026, 11, 26, 12, 0), "closed"),    # Thanksgiving (NYSE holiday)
        (et(2026, 12, 25, 12, 0), "closed"),    # Christmas (NYSE holiday)
        (et(2027, 1, 18, 12, 0), "closed"),     # MLK Day 2027 (NYSE holiday)
        (et(2026, 11, 27, 12, 59), "regular"),  # day after Thanksgiving: 1:00 pm early close
        (et(2026, 11, 27, 13, 0), "closed"),
        (et(2026, 12, 24, 13, 0), "closed"),    # Christmas Eve early close
        (et(2026, 12, 23, 13, 0), "regular"),   # ordinary day: still open at 1:00 pm
    ],
    ids=[
        "9:29", "9:30", "15:59", "16:00", "00:05", "08:09",
        "saturday", "sunday", "thanksgiving", "christmas", "mlk-2027",
        "early-close-12:59", "early-close-13:00", "christmas-eve-13:00", "normal-day-13:00",
    ],
)
def test_market_session(run_gate, when, session):
    out = run_gate(when, armed=True)
    assert out["market_session"] == session
    assert out["can_place_orders"] is (session == "regular")


def test_daylight_saving_time_is_handled(run_gate):
    # 13:30 UTC is 9:30 EDT in summer (open) but 8:30 EST in winter (closed).
    summer = run_gate(datetime(2026, 7, 8, 13, 30, tzinfo=UTC), armed=True)
    assert summer["market_session"] == "regular"
    assert summer["et_now"].endswith("EDT")

    winter = run_gate(datetime(2026, 12, 8, 13, 30, tzinfo=UTC), armed=True)
    assert winter["market_session"] == "closed"
    assert winter["et_now"].endswith("EST")

    winter_open = run_gate(datetime(2026, 12, 8, 14, 30, tzinfo=UTC), armed=True)
    assert winter_open["market_session"] == "regular"


# --- Heartbeat file ---------------------------------------------------------------

def test_heartbeat_flag_stamps_heartbeat_json(run_gate, state_dir):
    out = run_gate(TRADING_DAY_10AM, armed=True, heartbeat=True)
    hb = json.loads((state_dir / "heartbeat.json").read_text())
    assert hb == {
        "last_cycle": "2026-11-04T15:00:00Z",  # 10:00 EST in UTC
        "mode": out["mode"],
        "armed": out["armed"],
        "kill": out["kill"],
        "market_session": out["market_session"],
    }


def test_no_heartbeat_without_the_flag(run_gate, state_dir):
    run_gate(TRADING_DAY_10AM, armed=True)
    assert not (state_dir / "heartbeat.json").exists()
