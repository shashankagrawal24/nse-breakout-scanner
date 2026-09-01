"""Render one scan as a Slack Block Kit payload.

Pure formatting — no network, no files, no environment. The numbers are
whatever the pipeline computed; nothing here recalculates anything.

Slack's documented ceilings, all enforced below because breaching them
either returns 400 invalid_blocks or truncates silently:
    50 blocks per message | 3000 chars per section | 150 chars per header
"""
SECTION_MAX = 3000
HEADER_MAX = 150
BODY_MAX = 2900          # leaves room for the fence and label
MAX_ROWS = 25            # keeps one table inside one section

# (key, column header, suffix)
CONF_COLS = [("symbol", "SYMBOL", ""),
             ("close", "CLOSE", ""),
             ("breakout_level", "B/OUT", ""),
             ("vol_x_10wk", "VOL", "x"),
             ("base_months", "BASE", "m")]


def _esc(s: str) -> str:
    """Slack mrkdwn requires these three escaped; it is not Markdown."""
    return (str(s).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def _val(row, key, suffix):
    v = row.get(key)
    return "-" if v is None or v == "" else f"{v}{suffix}"


def _table(rows, cols):
    """Fixed-width table. Slack has no usable table block for this, so a
    monospace fence is the portable option."""
    grid = [[h for _, h, _ in cols]]
    grid += [[_val(r, k, s) for k, _, s in cols] for r in rows]
    widths = [max(len(r[i]) for r in grid) for i in range(len(cols))]
    lines = [_esc("  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip())
             for row in grid]
    return "\n".join(lines)


def _section(text):
    return {"type": "section",
            "text": {"type": "mrkdwn", "text": text[:SECTION_MAX]}}


def _table_section(label, rows, cols):
    if not rows:
        return _section(f"*{label}*\n_None._")
    shown, extra = rows[:MAX_ROWS], max(0, len(rows) - MAX_ROWS)
    body = _table(shown, cols)
    if len(body) > BODY_MAX:
        body = body[:BODY_MAX].rsplit("\n", 1)[0]
        extra = len(rows) - body.count("\n")
    more = f"\n_+{extra} more in the CSV_" if extra > 0 else ""
    return _section(f"*{label}* ({len(rows)})\n```\n{body}\n```{more}")


def build_slack_blocks(asof, confirmed, watch, link=""):
    """-> (fallback_text, blocks)

    Confirmed and watch only. The funnel, reject reasons and Claude note are
    still written to output/ every run — they are just not posted here.
    """
    provisional = any(r.get("weekly_candle_final") is False
                      for r in confirmed + watch)
    conf_names = ", ".join(r["symbol"] for r in confirmed) or "none"
    watch_names = ", ".join(r["symbol"] for r in watch) or "none"

    # Shown in the push notification and channel preview.
    fallback = (f"NSE breakout scan {asof} — {len(confirmed)} confirmed, "
                f"{len(watch)} watch\nCONFIRMED: {conf_names}\n"
                f"WATCH: {watch_names}")

    blocks = [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"NSE breakout scan {asof}"[:HEADER_MAX]}},
    ]
    if provisional:
        blocks.append(_section(
            ":hourglass_flowing_sand:  _Weekly candle still forming — every "
            "signal below is provisional until Friday's close._"))

    blocks.append(_table_section("Confirmed", confirmed, CONF_COLS))

    if watch:
        lines = "\n".join(
            f"• *{_esc(r['symbol'])}*  {_val(r, 'close', '')}  "
            f"— needs {_esc(r.get('s3_fail') or 'confirmation')}"
            for r in watch[:MAX_ROWS])
        blocks.append(_section(f"*Watch* ({len(watch)})\n{lines}"))
    else:
        blocks.append(_section("*Watch*\n_None._"))

    if link:
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"<{link}|Full output →>"}]})
    return fallback, blocks