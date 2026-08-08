"""Claude analysis layer with three authentication tiers.

Tier 1  ANTHROPIC_API_KEY        -> Anthropic SDK (pay-as-you-go API)
Tier 2  CLAUDE_CODE_OAUTH_TOKEN  -> Claude Code CLI in headless mode,
                                    billed to a Pro/Max subscription
                                    (generate once with: claude setup-token)
Tier 3  neither                  -> run.py writes analysis_prompt.txt; paste
                                    it into claude.ai manually for the note

The pipeline does all arithmetic; Claude only writes the narrative, grounded
strictly on the computed metrics. Docs: https://docs.claude.com/en/api/overview
"""
import json
import os
import shutil
import subprocess

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

SYSTEM = """You are a sceptical equity technical analyst writing an internal \
breakout note on Indian listed equities. You receive pre-computed metrics for \
stocks a deterministic pipeline has already classified. Rules, non-negotiable:
- Use ONLY the numbers provided. Never invent a price, level, date, or volume.
- Every invalidation level you state must be the provided breakout_level.
- For each CONFIRMED name write exactly 4 short lines: (1) what level was \
cleared and on what volume expansion, (2) base character from base_months and \
base_drawdown_pct — call a drawdown over 40% a recovery, not a base, (3) \
invalidation: a weekly close below breakout_level, (4) the single biggest \
concern (extension, base shape, thin turnover, or provisional weekly candle).
- For each WATCH name: one line on exactly what is missing.
- If weekly_candle_final is false, open the note by saying all signals are \
provisional until Friday's close.
- No buy/sell/target/position language. End with exactly: \
"Technical classification, not investment advice."
- Under 450 words. Plain prose, no markdown headers."""


def build_user_content(results: list, funnel: str) -> str:
    interesting = [r for r in results if r["bucket"] in ("CONFIRMED", "WATCH")]
    return ("Funnel summary:\n" + funnel +
            "\n\nClassified names (JSON):\n" + json.dumps(interesting, indent=1))


def _via_sdk(content: str):
    from anthropic import Anthropic
    msg = Anthropic().messages.create(
        model=MODEL, max_tokens=1500, system=SYSTEM,
        messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in msg.content if b.type == "text")


def _via_claude_code(content: str):
    """Headless Claude Code call, billed to the subscription behind
    CLAUDE_CODE_OAUTH_TOKEN."""
    exe = shutil.which("claude")
    if not exe:
        print("  CLAUDE_CODE_OAUTH_TOKEN set but `claude` CLI not installed")
        return None
    r = subprocess.run(
        [exe, "-p", "--output-format", "text"],
        input=SYSTEM + "\n\n---\n\n" + content,
        text=True, capture_output=True, timeout=420)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    print(f"  claude CLI failed (rc={r.returncode}): {r.stderr[:200]}")
    return None


def write_analysis(results: list, funnel: str) -> str | None:
    if not any(r["bucket"] in ("CONFIRMED", "WATCH") for r in results):
        return None
    content = build_user_content(results, funnel)
    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            print("  analysis via Anthropic API")
            return _via_sdk(content)
        if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            print("  analysis via Claude Code (subscription)")
            return _via_claude_code(content)
    except Exception as e:
        print(f"  Claude analysis failed: {type(e).__name__}: {e}")
    print("  no Claude credentials — writing analysis_prompt.txt instead")
    return None
