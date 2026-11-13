"""Tests for code/dashboard.py's performance math, run on the real logs in sample-data/.

The dashboard reads its state from a folder (dashboard.HOME, normally ~/.agentic-trader).
Each test points HOME at a temporary folder holding copies of the sample data, so the
live state folder is never read or written.

Note on counts: the dashboard counts exit rows in the ledger. A position sold as whole
shares plus a fractional remainder is logged as two exit rows, so "18 exits" here covers
fewer distinct picks.
"""
import json
from pathlib import Path

import pytest

import dashboard

SAMPLE_DATA = Path(__file__).resolve().parent.parent / "sample-data"

# The seven-week strategy review was on Aug 12, 2026; the next exit is Aug 17.
REVIEW_CUTOFF = "2026-08-13"


def read_jsonl(name):
    lines = (SAMPLE_DATA / name).read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def ledger_at_review():
    return [r for r in read_jsonl("ledger.jsonl") if r["ts"] < REVIEW_CUTOFF]


def with_original_aapl_bug(rows):
    """Put back the value the AAPL 2026-07-24 exit was first written with: 8.08 (percent-points)
    instead of 0.0808 (decimal). The sample data stores the corrected value."""
    fixed = [r for r in rows if r["symbol"] == "AAPL" and r["ts"].startswith("2026-07-24")]
    assert len(fixed) == 1 and fixed[0]["pnl_pct"] == pytest.approx(0.0808)
    return [dict(r, pnl_pct=8.08) if r is fixed[0] else r for r in rows]


@pytest.fixture
def home(tmp_path, monkeypatch):
    d = tmp_path / ".agentic-trader"
    d.mkdir()
    monkeypatch.setattr(dashboard, "HOME", d)
    return d


# --- Unit normalization --------------------------------------------------------------

@pytest.mark.parametrize(
    "stored, expected",
    [
        (8.08, 0.0808),      # percent-points -> decimal
        (-8.17, -0.0817),
        (-0.0817, -0.0817),  # already a decimal: unchanged
        (0.0059, 0.0059),
        (0, 0.0),
        (None, 0.0),         # entries have pnl_pct = null
        ("n/a", 0.0),
    ],
)
def test_pct_reads_both_units_as_a_decimal(stored, expected):
    assert dashboard._pct(stored) == pytest.approx(expected)


# --- Return math on the real ledger -------------------------------------------------

def test_review_date_numbers(home):
    """At the Aug 12 review the real figures were -3.37% per trade and about -$251 realized."""
    write_jsonl(home / "ledger.jsonl", ledger_at_review())
    d = dashboard.compute()
    assert d["n"] == 18
    assert len([e for e in d["exits"] if e["pnl_dollars"] > 0]) == 5
    assert d["realized"] == pytest.approx(-251.15)
    assert round(d["expectancy"], 2) == -3.37


def test_percent_point_row_does_not_flip_expectancy(home):
    """Regression test for the unit bug: one row stored as 8.08 instead of 0.0808 must not
    change the result. Before the fix, this row made a losing system read as profitable."""
    write_jsonl(home / "ledger.jsonl", with_original_aapl_bug(ledger_at_review()))
    d = dashboard.compute()
    assert round(d["expectancy"], 2) == -3.37
    assert round(d["avg_win"], 2) == 2.45  # the AAPL win counts as +8.08%, not +808%


def test_without_normalization_the_same_data_reads_as_profitable(home, monkeypatch):
    """Shows the regression test above has teeth: with the fix removed (raw values averaged,
    as before), the buggy row flips expectancy from about -3.4% to a large positive number."""
    monkeypatch.setattr(dashboard, "_pct", dashboard._f)
    write_jsonl(home / "ledger.jsonl", with_original_aapl_bug(ledger_at_review()))
    d = dashboard.compute()
    assert d["expectancy"] > 0
    assert d["avg_win"] > 100  # one row counted as +808%


def test_full_sample_ledger(home):
    write_jsonl(home / "ledger.jsonl", read_jsonl("ledger.jsonl"))
    d = dashboard.compute()
    assert d["n"] == 20
    assert d["realized"] == pytest.approx(-228.57)
    assert d["win_rate"] == pytest.approx(35.0)
    assert round(d["expectancy"], 2) == -2.56


def test_trades_from_before_arming_are_excluded(home):
    """The 4 positions inherited from the previous bot were sold at 15:10 on Jun 29,
    before the agent was armed. They must not count toward its track record."""
    rows = read_jsonl("ledger.jsonl")
    inherited = [r for r in rows if r["action"] == "exit" and r["ts"] < dashboard.ARMED_AT]
    assert {r["symbol"] for r in inherited} == {"MRVL", "TSM", "PANW", "VTI"}

    write_jsonl(home / "ledger.jsonl", rows)
    d = dashboard.compute()
    assert all(e["ts"] >= dashboard.ARMED_AT for e in d["exits"])
    assert d["n"] == len([r for r in rows if r["action"] == "exit"]) - len(inherited)


def test_alpha_vs_spy_comes_from_the_latest_equity_snapshot(home):
    write_jsonl(home / "equity.jsonl", read_jsonl("equity.jsonl"))
    d = dashboard.compute()
    assert d["alpha"] == pytest.approx(-327.41)  # last run, Aug 19


def test_open_pnl_from_positions(home):
    (home / "positions.json").write_text(json.dumps({
        "UP": {"entry": 100, "last_price": 110, "dollars": 500},    # +10% of $500 = +$50
        "DOWN": {"entry": 50, "last_price": 45, "dollars": 200},    # -10% of $200 = -$20
        "NOQUOTE": {"entry": 10, "dollars": 100},                   # no last price: skipped
    }))
    assert dashboard.compute()["open_pnl"] == pytest.approx(30.0)


def test_empty_state_folder_gives_zeros(home):
    d = dashboard.compute()
    assert (d["n"], d["realized"], d["expectancy"], d["open_pnl"]) == (0, 0, 0.0, 0)
    assert d["alpha"] is None


# --- The HTML dashboard -------------------------------------------------------------

@pytest.mark.parametrize(
    "flags, badge",
    [
        ((), "DRY RUN — places nothing"),
        (("ARMED",), "ARMED — live trading"),
        (("ARMED", "KILL"), "KILL ENGAGED — halted"),
    ],
    ids=["dry-run", "armed", "kill"],
)
def test_status_badge_follows_the_flag_files(home, flags, badge):
    for name in flags:
        (home / name).touch()
    assert badge in dashboard.html(dashboard.compute())


def test_dashboard_renders_review_numbers(home):
    write_jsonl(home / "ledger.jsonl", with_original_aapl_bug(ledger_at_review()))
    write_jsonl(home / "equity.jsonl", read_jsonl("equity.jsonl"))
    page = dashboard.html(dashboard.compute())
    assert ">-3.37%<" in page          # expectancy card
    assert "$-251.15" in page          # realized P&L card
    assert "+0.34%" not in page


def test_main_writes_the_dashboard_into_the_state_folder(home, capsys):
    write_jsonl(home / "ledger.jsonl", read_jsonl("ledger.jsonl"))
    dashboard.main()
    assert (home / "dashboard.html").read_text().startswith("<!doctype html>")
    assert "expectancy -2.56%/trade" in capsys.readouterr().out
