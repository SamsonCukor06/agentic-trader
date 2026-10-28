#!/usr/bin/env python3
"""
Agentic Trader — home base dashboard generator.

Pure stdlib, reads only the JSON state in ~/.agentic-trader/ (off iCloud), and
writes a self-contained dashboard.html. Run it directly for a terminal summary,
or let the trade-cycle skill regenerate it each cycle:

    python3 ~/.agentic-trader/dashboard.py && open ~/.agentic-trader/dashboard.html

Data files it reads (all optional; missing = empty):
  positions.json     open positions: {SYMBOL: {entry, stop, target, last_price, thesis, opened}}
  ledger.jsonl       one line per fill: {ts, action:"enter"|"exit", symbol, price, dollars,
                                         pnl_dollars, pnl_pct, reason, thesis}
  decisions.jsonl    one line per cycle: {ts, regime, deployable, screened, picks:[{ticker,thesis}],
                                          managed:[...], armed}
  equity.jsonl       one line per cycle: {ts, deployable, total_value, open_pnl}
  heartbeat.json     {last_cycle, armed, kill}
"""
import json, datetime as dt
from pathlib import Path

HOME = Path.home() / ".agentic-trader"


def _jsonl(name):
    p = HOME / name
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _json(name, default):
    p = HOME / name
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


# ledger.jsonl stores pnl_pct as a decimal fraction (-0.0817 = -8.17%), but a few
# rows were written as percent-points (AAPL 2026-07-24 stored 8.08 for +8.08%).
# Averaging those raw made one row count as +808% and flipped reported expectancy
# positive. Normalize on read: |x| >= 1 means the row is in percent-points.
def _pct(v, d=0.0):
    x = _f(v, d)
    return x / 100.0 if abs(x) >= 1.0 else x


# Positions inherited from the predecessor bot were liquidated at arming
# (2026-06-29T15:10). Those exits are not this system's trades and must not
# score its track record.
ARMED_AT = "2026-06-29T15:29"


def _ago(iso):
    if not iso:
        return "never"
    try:
        t = dt.datetime.fromisoformat(iso)
        now = dt.datetime.now(t.tzinfo)
        secs = (now - t).total_seconds()
        if secs < 90:
            return f"{int(secs)}s ago"
        if secs < 5400:
            return f"{int(secs//60)}m ago"
        if secs < 172800:
            return f"{int(secs//3600)}h ago"
        return f"{int(secs//86400)}d ago"
    except Exception:
        return iso


def compute():
    positions = _json("positions.json", {})
    ledger = _jsonl("ledger.jsonl")
    decisions = _jsonl("decisions.jsonl")
    equity = _jsonl("equity.jsonl")
    armed = (HOME / "ARMED").exists()
    kill = (HOME / "KILL").exists()
    hb = _json("heartbeat.json", {})

    exits = [e for e in ledger
             if e.get("action") == "exit" and (e.get("ts") or "") >= ARMED_AT]
    wins = [e for e in exits if _f(e.get("pnl_dollars")) > 0]
    losses = [e for e in exits if _f(e.get("pnl_dollars")) < 0]
    n = len(exits)
    win_rate = (len(wins) / n * 100) if n else 0.0
    avg_win = (sum(_pct(e["pnl_pct"]) for e in wins) / len(wins) * 100) if wins else 0.0
    avg_loss = (sum(_pct(e["pnl_pct"]) for e in losses) / len(losses) * 100) if losses else 0.0
    realized = sum(_f(e.get("pnl_dollars")) for e in exits)
    expectancy = (win_rate / 100 * avg_win + (1 - win_rate / 100) * avg_loss) if n else 0.0

    last_eq = equity[-1] if equity else {}
    open_pnl = sum(
        (_f(p.get("last_price")) - _f(p.get("entry"))) /
        _f(p.get("entry"), 1) * _f(p.get("dollars"), 0)
        for p in positions.values() if p.get("last_price") and p.get("entry")
    )

    # v3 risk state: factor breaker, cooldown, factor exposure, SPY alpha
    factor_state = _json("factor_state.json", {}).get("factors", {})
    breakers = [f"{name}: DERATING (stab {info.get('stabilization_sessions', 0)}/3)"
                for name, info in factor_state.items() if info.get("derating_active")]
    checkpoints = _json("checkpoints.json", {})
    cooldown = checkpoints.get("entry_cooldown_until")
    # factor exposure by dollars (positions tagged with a `factor`; default OTHER)
    factor_expo = {}
    for p in positions.values():
        fac = p.get("factor") or "OTHER"
        factor_expo[fac] = factor_expo.get(fac, 0.0) + _f(p.get("dollars"))
    alpha = _f(last_eq.get("alpha_dollars")) if last_eq.get("alpha_dollars") is not None else None

    return dict(positions=positions, ledger=ledger, decisions=decisions, equity=equity,
                armed=armed, kill=kill, hb=hb, exits=exits, n=n, win_rate=win_rate,
                avg_win=avg_win, avg_loss=avg_loss, realized=realized, expectancy=expectancy,
                last_eq=last_eq, open_pnl=open_pnl, breakers=breakers, cooldown=cooldown,
                factor_expo=factor_expo, alpha=alpha)


def _sparkline(equity, w=520, h=60):
    vals = [_f(e.get("total_value") or e.get("deployable")) for e in equity if e]
    vals = [v for v in vals if v > 0]
    if len(vals) < 2:
        return '<div class="muted">equity curve appears after a few cycles</div>'
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i/(len(vals)-1)*w:.1f},{h-(v-lo)/rng*h:.1f}" for i, v in enumerate(vals))
    up = vals[-1] >= vals[0]
    color = "var(--green)" if up else "var(--red)"
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/></svg>')


def _risk_state_html(d):
    breakers = d["breakers"]
    bk = " · ".join(breakers) if breakers else "no factor deratings active"
    cd = d["cooldown"]
    cd_txt = f"cooldown until {cd}" if cd else "cooldown: clear"
    expo = d["factor_expo"]
    total = sum(expo.values()) or 1
    expo_txt = " · ".join(f"{fac} {v/total*100:.0f}%" for fac, v in
                          sorted(expo.items(), key=lambda kv: -kv[1])) or "no positions"
    bk_cls = "red" if breakers else "green"
    cd_cls = "amber" if cd else "green"
    return (f"<span class='rs-lbl'>factor breaker</span> <span class='{bk_cls}'>{bk}</span>"
            f"<span class='rs-sep'>│</span><span class='rs-lbl'>{cd_txt.split(':')[0] if ':' in cd_txt else 'cooldown'}</span> "
            f"<span class='{cd_cls}'>{cd_txt}</span>"
            f"<span class='rs-sep'>│</span><span class='rs-lbl'>factor exposure</span> "
            f"<span class='muted'>{expo_txt}</span>")


def html(d):
    pos, hb = d["positions"], d["hb"]
    if d["kill"]:
        status, scls = "KILL ENGAGED — halted", "kill"
    elif d["armed"]:
        status, scls = "ARMED — live trading", "armed"
    else:
        status, scls = "DRY RUN — places nothing", "dry"
    last_cycle = _ago(hb.get("last_cycle"))

    def money(v, sign=False):
        v = _f(v)
        s = f"{'+' if sign and v >= 0 else ''}{v:,.2f}"
        return s

    def cls(v):
        return "green" if _f(v) > 0 else ("red" if _f(v) < 0 else "")

    # position rows
    prows = ""
    for sym, p in sorted(pos.items()):
        entry, stop, tgt = _f(p.get("entry")), _f(p.get("stop")), _f(p.get("target"))
        last = _f(p.get("last_price"))
        pnl = ((last - entry) / entry * 100) if (last and entry) else None
        to_stop = ((last - stop) / last * 100) if (last and stop) else None
        prows += (
            f"<tr><td class='sym'>{sym}</td><td>{entry:.2f}</td>"
            f"<td>{('%.2f'%last) if last else '—'}</td>"
            f"<td class='{cls(pnl) if pnl is not None else ''}'>{('%+.1f%%'%pnl) if pnl is not None else '—'}</td>"
            f"<td>{stop:.2f}</td><td>{tgt:.2f}</td>"
            f"<td class='muted'>{('%.1f%% to stop'%to_stop) if to_stop is not None else ''}</td>"
            f"<td class='thesis'>{(p.get('thesis') or '')[:90]}</td></tr>"
        )
    if not prows:
        prows = "<tr><td colspan='8' class='muted'>no open positions</td></tr>"

    # decisions (thought process)
    drows = ""
    for c in reversed(d["decisions"][-6:]):
        picks = c.get("picks") or []
        pk = ", ".join(p.get("ticker", "?") for p in picks) or "stayed flat"
        drows += (f"<div class='dcard'><div class='drow'><span class='dtime'>{_ago(c.get('ts'))}</span>"
                  f"<span class='badge'>{c.get('regime','?')}</span>"
                  f"<span class='muted'>screened {c.get('screened','?')} · armed={c.get('armed')}</span></div>"
                  f"<div class='dpicks'><b>{pk}</b></div>")
        for p in picks[:4]:
            drows += f"<div class='thesis2'>• <b>{p.get('ticker','')}</b>: {(p.get('thesis') or '')[:160]}</div>"
        drows += "</div>"
    if not drows:
        drows = "<div class='muted'>No cycles logged yet. Run a trading cycle to populate this.</div>"

    # recent trades
    trows = ""
    for e in reversed(d["ledger"][-12:]):
        act = e.get("action", "")
        pnl = e.get("pnl_pct")
        pnlcell = f"<span class='{cls(pnl)}'>{_f(pnl):+.1f}%</span>" if act == "exit" and pnl is not None else ""
        trows += (f"<tr><td class='muted'>{_ago(e.get('ts'))}</td>"
                  f"<td class='{'green' if act=='enter' else 'red'}'>{act.upper()}</td>"
                  f"<td class='sym'>{e.get('symbol','')}</td><td>{_f(e.get('price')):.2f}</td>"
                  f"<td>{pnlcell}</td><td class='thesis'>{(e.get('reason') or e.get('thesis') or '')[:80]}</td></tr>")
    if not trows:
        trows = "<tr><td colspan='6' class='muted'>no trades yet</td></tr>"

    le = d["last_eq"]
    deployable = _f(le.get("deployable"))
    total_val = _f(le.get("total_value"))
    gen = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Agentic Trader</title><style>
:root{{--bg:#0d1117;--card:#161b22;--bd:#30363d;--fg:#e6edf3;--mut:#8b949e;
--green:#3fb950;--red:#f85149;--amber:#d29922;--blue:#58a6ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:24px}}
h1{{font-size:20px;margin:0}}h2{{font-size:13px;text-transform:uppercase;letter-spacing:.06em;
color:var(--mut);margin:24px 0 10px}}.wrap{{max-width:960px;margin:0 auto}}
.top{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
.status{{padding:6px 12px;border-radius:20px;font-weight:600;font-size:13px}}
.armed{{background:rgba(63,185,80,.15);color:var(--green);border:1px solid var(--green)}}
.dry{{background:rgba(210,153,34,.12);color:var(--amber);border:1px solid var(--amber)}}
.kill{{background:rgba(248,81,73,.15);color:var(--red);border:1px solid var(--red)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-top:16px}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px}}
.card .lbl{{color:var(--mut);font-size:12px}}.card .val{{font-size:22px;font-weight:700;margin-top:4px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--bd);
border-radius:10px;overflow:hidden}}th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid var(--bd)}}
th{{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
tr:last-child td{{border-bottom:none}}.sym{{font-weight:700;color:var(--blue)}}
.green{{color:var(--green)}}.red{{color:var(--red)}}.muted{{color:var(--mut)}}
.thesis,.thesis2{{color:var(--mut);font-size:12.5px}}.thesis{{max-width:240px}}
.dcard{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px;margin-bottom:10px}}
.drow{{display:flex;gap:10px;align-items:center}}.dtime{{color:var(--mut);font-size:12px;min-width:64px}}
.badge{{background:rgba(88,166,255,.12);color:var(--blue);padding:2px 8px;border-radius:6px;font-size:12px}}
.dpicks{{margin:6px 0}}.thesis2{{margin:3px 0 0 8px}}.spark{{background:var(--card);border:1px solid var(--bd);
border-radius:10px;padding:12px;margin-top:10px}}.foot{{color:var(--mut);font-size:11px;margin-top:24px;text-align:center}}
.riskstate{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:10px 14px;
margin-top:12px;font-size:12.5px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
.rs-lbl{{color:var(--mut);text-transform:uppercase;font-size:10.5px;letter-spacing:.05em}}
.rs-sep{{color:var(--bd);margin:0 6px}}
</style></head><body><div class="wrap">
<div class="top"><div><h1>⚡ Agentic Trader</h1>
<div class="muted">agentic account (agentic) · last cycle {last_cycle}</div></div>
<div class="status {scls}">{status}</div></div>

<div class="cards">
<div class="card"><div class="lbl">Deployable</div><div class="val">${money(deployable)}</div></div>
<div class="card"><div class="lbl">Account value</div><div class="val">${money(total_val)}</div></div>
<div class="card"><div class="lbl">Open P&amp;L</div><div class="val {cls(d['open_pnl'])}">${money(d['open_pnl'],True)}</div></div>
<div class="card"><div class="lbl">Realized P&amp;L</div><div class="val {cls(d['realized'])}">${money(d['realized'],True)}</div></div>
<div class="card"><div class="lbl">Win rate</div><div class="val">{d['win_rate']:.0f}%<span class="muted" style="font-size:13px"> ({d['n']})</span></div></div>
<div class="card"><div class="lbl">Expectancy/trade</div><div class="val {cls(d['expectancy'])}">{d['expectancy']:+.2f}%</div></div>
<div class="card"><div class="lbl">Alpha vs SPY</div><div class="val {cls(d['alpha']) if d['alpha'] is not None else ''}">{('$'+money(d['alpha'],True)) if d['alpha'] is not None else '—'}</div></div>
</div>

<div class="riskstate">{_risk_state_html(d)}</div>

<h2>Equity</h2><div class="spark">{_sparkline(d['equity'])}</div>

<h2>Open positions</h2>
<table><tr><th>Sym</th><th>Entry</th><th>Last</th><th>P&amp;L</th><th>Stop</th><th>Target</th><th></th><th>Thesis</th></tr>{prows}</table>

<h2>Recent decisions — the bot's thinking</h2>{drows}

<h2>Trade log</h2>
<table><tr><th>When</th><th>Action</th><th>Sym</th><th>Price</th><th>P&amp;L</th><th>Reason</th></tr>{trows}</table>

<div class="foot">generated {gen} · auto-refreshes every 60s · win rate over {d['n']} closed trades · avg win {d['avg_win']:+.1f}% / avg loss {d['avg_loss']:+.1f}%</div>
</div></body></html>"""


def terminal(d):
    mode = "KILL" if d["kill"] else ("ARMED" if d["armed"] else "DRY RUN")
    print(f"\n  AGENTIC TRADER  [{mode}]  last cycle: {_ago(d['hb'].get('last_cycle'))}")
    print(f"  deployable ${_f(d['last_eq'].get('deployable')):,.2f} · open P&L ${d['open_pnl']:+,.2f} "
          f"· realized ${d['realized']:+,.2f}")
    print(f"  win rate {d['win_rate']:.0f}% over {d['n']} trades · expectancy {d['expectancy']:+.2f}%/trade"
          + (f" · alpha vs SPY ${d['alpha']:+,.2f}" if d['alpha'] is not None else ""))
    bk = " · ".join(d["breakers"]) if d["breakers"] else "none active"
    cd = f"cooldown until {d['cooldown']}" if d["cooldown"] else "cooldown clear"
    print(f"  factor breaker: {bk} · {cd}")
    print(f"  open positions: {', '.join(d['positions'].keys()) or '(none)'}\n")


def main():
    d = compute()
    out = HOME / "dashboard.html"
    out.write_text(html(d))
    terminal(d)
    print(f"  dashboard -> {out}")


if __name__ == "__main__":
    main()
