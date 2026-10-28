# STRATEGY REVIEW — 2026-07-16 (on-demand, read-only)

**model:** claude-fable-5 · **trigger:** user-requested (formal 20-episode checkpoint NOT yet due — 12 closed episodes; leg-level rows = 20) · **constraint:** analysis only — no thresholds changed, no checkpoints stamped, no shadow grades written back, no alerts fired.

## Headline verdict

**The OLD strategy (pre-7/8 entries) is measured and it lost. The CURRENT strategy (v3 gates + v4 80/20, post-7/8) has produced ZERO active entries and therefore has an empty sample — it cannot be evaluated yet.** Recommendation: freeze the rulebook and let it accumulate data. Do not change rules, size, or arm-state on this evidence.

---

## 1. LIVE scorecard (all closed since arming 6/29)

| Basis | Trades | Win rate | Avg win | Avg loss | Expectancy | Profit factor |
|---|---|---|---|---|---|---|
| Per leg (ledger rows) | 20 | 40% | +3.37% | −5.24% | **−1.80%/trade** | 0.44 |
| Per episode, strategy only (excl. 6/29 user-directed liquidation) | 8 | **25%** | +$9.02 | −$39.64 | **−$27.48/episode** | 0.24 |

- **Alpha vs SPY-and-sit since inception (6/29): −$234.83.** **The bot has NOT beaten buy-and-hold** — the predecessor's fatal flaw, still unresolved on the current sample.
- Realized strategy P&L: **−$219.82**. User-directed liquidation legs (6/29): +$63.76. AAPL trim (7/13): +$16.51. Net ledger: −$139.55.
- Account: $4,262.20 vs $4,435.61 at arming (−3.9%). Drawdown from all-time peak: 7.3% (breaker off, <8% resume line).

## 2. Era decomposition (the key finding)

| Era | Active entries | Closed result |
|---|---|---|
| Pre-guardrail (6/29–7/7) | 8 | **−$219.82** — all 6 losing episodes; 5 of 6 = the same trade (AI/semi long into an active factor derating) |
| v3 era (post-7/8 fixes) | **0** | n/a — every candidate since 7/8 blocked by factor-breaker / anti-chase / caps; only SPY/SGOV baseline bought (7/13–14) |

Every closed trade in the negative-expectancy sample was entered before the factor-breaker, loss-streak cooldown, and whole-share-floor existed. The negative-expectancy tripwire targets a strategy that keeps producing losers; this one has instead produced six consecutive trade-free days. **Treat 2026-07-08 as inception for judging the current strategy.**

## 3. Conviction calibration table

| Conviction bucket | Closed trades | Result |
|---|---|---|
| ≤6.5 | AAPL (6.5) | WIN (+6.66% trim banked; remainder +10% open) |
| 7–7.5 | SPCX re-entry (7), MU (7.5) | LOSS −8.16%, LOSS −7.64% |
| not logged (pre-7/2 gap) | UI, LRCX, AMD, META, PLTR, SPCX#1 | 5L / 1W — unratable |

Directionally INVERTED (higher conviction → worse outcomes) but n=3 rated closed trades = noise, not calibration. Real finding: conviction wasn't logged on the first 6 entries (gap fixed 7/2). Sizing off conviction remains statistically unproven; revisit at ~10+ rated closed episodes.

## 4. Shadow-ledger verdict per filter (23 rows; recent grades computed IN-MEMORY only, not written back)

| Filter | Saved | Cost | Verdict |
|---|---|---|---|
| factor-breaker | 1 confirmed: **MU** (blocked 7/14 @975.77 → 861.64, through its would-be stop ≈ −$75 avoided) + NVDA leaning saved (207 vs 211.80 entry) | 0 | **Earning its place** — early but clean |
| anti-chase | 2 formal (RIVN, SOFI) + HOOD now through its would-be stop (107.26 vs 108 stop) | **~2, BOTH SOXS** | Mostly right; one systematic blind spot (below) |
| caps | — (COIN 7/6, LLY ×2, GS all open/flat) | — | No verdict yet |
| conviction | — (COIN 7/2, COP open) | — | No verdict yet |

**The SOXS pattern (watch item):** the system correctly diagnosed the AI derating for two weeks but every attempt to monetize it via the inverse ETF arrived after a multi-percent down-move and was anti-chase-rejected. The 7/14 rejection (@~42.5 split-adjusted) has since cleared its would-be target (~+20%); the 7/13 rejection is well in the money. Both grades are informal until the formal ≥5-day path-check (SOXS reverse-split since logging; prices split-adjusted here). If formal grading confirms "cost," the next review should consider a narrow carve-out for initiating inverse-ETF positions EARLY in a confirmed derating. **Not changed now.**

## 5. Dominant shapes (lessons.jsonl, 11 post-mortems)

- **Losing shape (5 of 6 strategy losses):** long an AI-complex name into an active factor derating — extended/breakout entries, stopped within ~24h (UI, LRCX, AMD, META, MU). Exactly what the breaker now blocks.
- **Winning shapes:** factor-independent thesis (AAPL — pricing power, not AI-capex); trailing stops banking gains without needing the "why" (SPCX#1, PLTR); scale-out at target instead of round-tripping (AAPL trim — the direct SPCX fix).
- **Event-flow rule reinforced:** exit index-inclusion trades INTO the effective date (SPCX#2 −8.2% for holding past it).

## 6. Suggestions (NONE applied — user to accept/reject)

1. **Freeze the rulebook.** Three strategy changes in 10 days (7/8 v3 gates, 7/13 v4 80/20, trail-rule rework) keep resetting the evidence clock. No new rules until ~10 closed v3-era episodes or ~3–4 weeks.
2. **Report eras separately** in future reviews (pre-7/8 vs post-7/8) so legacy losses stop dominating the headline stats.
3. **Acknowledge the current posture:** with AI+crypto breakers on, the account is functionally SPY/SGOV + two legacy AI longs (AAPL, GOOGL). Coherent capital preservation; alpha recovery depends on AAPL/GOOGL or the breaker lifting.
4. **SOXS/anti-chase carve-out is the one candidate refinement** — decide at the next review, on formal shadow grades, not now.
5. **Keep LIVE at current size.** The protocol's negative-expectancy clause suggests dry-run, but the exposure it protects against is already ~zero (no new entries in 6 days, resting stops under both actives, ~20% cash + ~55% baseline). De-arming would mostly stop the data clock. The 25%-win-rate/0.24-PF numbers belong to a strategy version that no longer exists.

## Status of protocol checkpoints at review time

- Review checkpoint: not formally due (12 closed episodes < 20); `last_review_count` left at 0 — untouched.
- Drawdown breaker: OFF (7.3% from peak < 12% trip, < 8% resume).
- Loss-streak cooldown: clear (`consecutive_closed_losses` = 1; `entry_cooldown_until` 2026-07-08, expired).
- Factor breakers: AI_COMPLEX DERATING (since 6/30, stab 0/3), CRYPTO DERATING (since 6/1, 0/3).
