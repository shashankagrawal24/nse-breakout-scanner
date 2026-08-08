# NSE Breakout Scanner

Scheduled automation that pulls three NSE live-analysis feeds every trading
evening — 52-week highs, volume gainers, price gainers — merges them into one
candidate list, runs a deterministic breakout-confirmation pipeline on weekly
and monthly OHLC, and writes a CSV of confirmed breakout tickers plus a
Claude-written analysis note.

## How the intelligence is split

The identification and confirmation math is plain Python, not an LLM call.
IF a filter is arithmetic (close off high, volume multiple, base length,
moving averages), THEN it runs in code so the same stock passes or fails
identically every night and costs nothing. Claude (Application Programming
Interface call, model `claude-sonnet-4-6`) is used only for the final
analysis note, and it is given the pre-computed metrics as its only source
of truth — it is instructed to never invent a price or level. That makes the
narrative useful and the numbers un-hallucinatable.

## Pipeline

1. Stage 0 — universe: EQ series only, no ETFs/index funds, turnover >= Rs 5 cr
2. Stage 1 — pre-screen: reject red closes, closes >3% off the day high, and
   bases <= 10 days (rolling highs, i.e. already trending)
3. Stage 2 — fetch ~2 years of daily OHLCV per survivor (yfinance); NSE's
   official close/high is spliced in when Yahoo's same-day India bar is null
4. Stage 3 — weekly confirmation: close above the prior 52-week max weekly
   close, close in the upper third of the week's range, volume >= 1.5x the
   10-week average, price above a rising 30-week MA (all four must pass)
5. Stage 4 — monthly qualification: base >= 3 months, monthly close above the
   base's max monthly close, <= +25% over the 10-month MA, base drawdown <= 50%
6. Stage 5 — CONFIRMED (Stage 3 all + Stage 4 >= 3/4), WATCH, or REJECTED

Runs before Friday's close are marked `weekly_candle_final = False` because
the weekly candle is still forming; Friday runs are final.

## Setup (GitHub Actions) — no credentials needed

1. Create a repo and push this folder.
2. (Optional) Repo Settings -> Secrets and variables -> Actions -> add
   `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for the evening summary ping.
   `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` are NOT required — see
   "No API key?" below.
3. Actions tab -> NSE Breakout Scanner -> Run workflow (manual test).
4. The schedule (`30 12 * * 1-5` = 18:00 IST weekdays) then runs itself.
   The scanner reads the feed timestamp and dates the output folder to the
   trading day, so a Saturday run of Friday's frozen data files correctly.

Each run commits `output/YYYY-MM-DD/` back to the repo:

- `breakouts_confirmed.csv` — the tickers you asked for, with metrics
- `watchlist.csv`, `rejects.csv`, `funnel.txt`, `all_results.json`
- `analysis_prompt.txt` — paste into claude.ai for the analysis note
  (becomes `analysis.md` automatically if you ever add Claude credentials)
- `raw/*.json` — the untouched NSE payloads, for audit

`output/latest/` always mirrors the most recent scan, so
`.../output/latest/analysis_prompt.txt` is a stable, bookmarkable path — the
Telegram summary includes the link automatically. IF the repo is public,
THEN you can also just give Claude in claude.ai the raw link
(`https://raw.githubusercontent.com/<user>/<repo>/main/output/latest/analysis_prompt.txt`)
and ask it to fetch and analyse — no copy-paste at all.

## No API key? Two free options

The scanner never needed the key for the actual breakout logic — that is
deterministic code. The key only produced the written analysis note. IF you
do not have an API key, THEN pick one of these:

1. **Claude subscription token (best if you are on the Pro or Max plan).**
   Run `claude setup-token` once on your own machine (requires the Claude
   Code command line tool), copy the token it prints, and add it as a GitHub
   secret named `CLAUDE_CODE_OAUTH_TOKEN`. The workflow detects it, installs
   Claude Code on the runner, and writes the analysis using your existing
   subscription quota — no API account, no separate billing.
2. **Manual paste (zero setup).** With no credentials at all, each run writes
   `analysis_prompt.txt` next to the tickers CSV. Open it, paste the contents
   into claude.ai, and you get the identical note — it contains the exact
   same instructions the API call would have used.

IF both secrets are absent, THEN nothing fails: the confirmed tickers CSV,
watchlist, rejects log, and Telegram summary are all produced regardless.

## Offline / backtest mode

Feed it the CSVs downloaded manually from the NSE website:

```
python run.py --offline --csv52 52WeekHigh.csv \
  --csvvol LA-Volume-Gainers-07-Aug-2026.csv --asof 2026-08-07
```

## Known failure modes

- **NSE blocking.** NSE's Akamai sometimes 403s datacenter IPs. The fetcher
  bootstraps cookies, retries with backoff, and refreshes the session; the
  API often responds even when the homepage 403s. IF runs start failing
  consistently with all-feeds-failed, THEN switch to a machine on a
  residential IP — on Windows:
  `schtasks /Create /SC WEEKLY /D MON,TUE,WED,THU,FRI /TN "NSE Breakout Scan" /TR "cmd /c cd /d C:\path\nse-breakout-scanner && set PYTHONUTF8=1 && python run.py" /ST 18:00`
- **Yahoo EOD lag.** Yahoo's India daily bar is often null on the evening of
  the trading day; the pipeline splices NSE's official LTP/high so the tests
  still run on real closes. Volume on that bar is Yahoo's own live figure.
- **Holidays.** Feeds return the previous session; the timestamp-based
  dating means the run just re-writes that day's folder with no side effects.
- **Field names.** NSE's 52-week-high API really does spell the field
  `comapnyName`. The parser handles both spellings in case they fix it.

Outputs are technical classification, not investment advice.
