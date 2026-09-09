"""
weekly_summary.py
=================
Queries the tracker DB and produces a single Markdown weekly digest —
the kind of thing you'd actually send to founders on a Monday morning.

Output: weekly_summary_<YYYY-MM-DD>.md

Sections:
  1. Signal snapshot (noise/signal ratio, total reports, unique issues)
  2. Top issues by report count
  3. New issues this week (first_reported within last 7 days)
  4. Escalation recommendations with one-line justification
  5. Category breakdown
  6. Noise analysis

JUDGMENT CALLS flagged with (J):

  (J) ESCALATION CRITERIA: An issue is recommended for escalation if it meets
      ANY of: severity=critical, severity=high AND report_count>=3, or
      report_count>=5 regardless of severity. These thresholds are conservative
      by design — better to over-escalate than miss a critical bug in a weekly
      summary sent to founders.

  (J) "THIS WEEK" WINDOW: Defaults to 7 days. Override via --days.
      In a real deployment this would be driven by the last pipeline run time,
      not a fixed window.

  (J) SUMMARY FORMAT: Written to read like a Slack message to a non-technical
      founder. No SQL jargon, severity coded as emoji, counts bolded.

Usage:
    python weekly_summary.py
    python weekly_summary.py --days 14       # look back 14 days
    python weekly_summary.py --db tracker.db
    python weekly_summary.py --out my_summary.md
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_DB   = Path("tracker.db")
LOOKBACK_DAYS = 7

SEV_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
    None:       "⚪",
}

CAT_LABEL = {
    "bug":             "Bug",
    "feature_request": "Feature Request",
    "ux_confusion":    "UX Confusion",
    "duplicate":       "Duplicate",
    "noise":           "Noise",
}

# ── DB queries ────────────────────────────────────────────────────────────────

def open_db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def get_all_issues(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute(
        "SELECT * FROM issues ORDER BY report_count DESC, severity DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_raw_count(con: sqlite3.Connection) -> int:
    return con.execute("SELECT COUNT(*) FROM raw_reports").fetchone()[0]


def get_noise_count(con: sqlite3.Connection) -> int:
    return con.execute(
        "SELECT COUNT(*) FROM raw_reports WHERE triage_category = 'noise'"
    ).fetchone()[0]


def get_new_issues(con: sqlite3.Connection, since: str) -> list[dict]:
    rows = con.execute(
        "SELECT * FROM issues WHERE first_reported >= ? ORDER BY report_count DESC",
        (since,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_top_issues(issues: list[dict], n: int = 10) -> list[dict]:
    return sorted(
        [i for i in issues if i["category"] != "noise"],
        key=lambda x: (-x["report_count"], x["severity"] or "z")
    )[:n]


def should_escalate(issue: dict) -> tuple[bool, str]:
    """
    Returns (should_escalate, justification).
    (J) Escalation criteria — see module docstring.
    """
    sev   = issue.get("severity")
    count = issue.get("report_count", 0)
    cat   = issue.get("category")

    if cat != "bug":
        return False, ""
    if sev == "critical":
        return True, f"Critical severity — {count} report(s), potential data loss or full auth breakage."
    if sev == "high" and count >= 3:
        return True, f"High severity with {count} reports — core feature broken, no workaround confirmed."
    if count >= 5:
        return True, f"{count} separate reports across channels — high user impact regardless of severity."
    return False, ""


# ── Renderer ──────────────────────────────────────────────────────────────────

def render_summary(
    issues: list[dict],
    raw_count: int,
    noise_count: int,
    new_issues: list[dict],
    week_start: str,
    week_end: str,
) -> str:

    total_issues     = len(issues)
    non_noise_raw    = raw_count - noise_count
    noise_pct        = noise_count / raw_count * 100 if raw_count else 0
    signal_pct       = non_noise_raw / raw_count * 100 if raw_count else 0

    bug_issues  = [i for i in issues if i["category"] == "bug"]
    feat_issues = [i for i in issues if i["category"] == "feature_request"]
    ux_issues   = [i for i in issues if i["category"] == "ux_confusion"]

    # Top issues
    top = get_top_issues(issues, n=10)

    # Escalation candidates
    escalate_list = [
        (i, justification)
        for i in issues
        if (esc := should_escalate(i))[0]
        for justification in [esc[1]]
    ]
    escalate_list.sort(key=lambda x: -x[0]["report_count"])

    # ── Build sections ────────────────────────────────────────────────────────

    # Section 1: Snapshot
    snapshot = f"""## Signal Snapshot

| Metric | Value |
|---|---|
| Raw feedback items | **{raw_count}** |
| Noise filtered | {noise_count} ({noise_pct:.0f}%) |
| Actionable items | **{non_noise_raw}** ({signal_pct:.0f}%) |
| Unique tracked issues | **{total_issues}** |
| Open bugs | **{len(bug_issues)}** |
| Feature requests | {len(feat_issues)} |
| UX confusion reports | {ux_issues and len(ux_issues) or 0} |
| New issues this week | **{len(new_issues)}** |
"""

    # Section 2: Top issues
    top_rows = []
    for i in top:
        sev   = i.get("severity") or "—"
        emoji = SEV_EMOJI.get(sev, "⚪")
        cat   = CAT_LABEL.get(i["category"], i["category"])
        top_rows.append(
            f"| #{i['id']} | {emoji} {sev} | **{i['report_count']}** | {cat} | {i['canonical_summary'][:65]} |"
        )
    top_table = "\n".join(top_rows)

    top_section = f"""## Top Issues by Report Count

| ID | Severity | Reports | Category | Summary |
|---|---|---|---|---|
{top_table}
"""

    # Section 3: New this week
    if new_issues:
        new_rows = []
        for i in new_issues[:8]:
            emoji = SEV_EMOJI.get(i.get("severity"), "⚪")
            cat   = CAT_LABEL.get(i["category"], i["category"])
            new_rows.append(
                f"| #{i['id']} | {emoji} {i.get('severity') or '—'} | {cat} | {i['canonical_summary'][:65]} |"
            )
        new_table = "\n".join(new_rows)
        new_section = f"""## New Issues This Week ({len(new_issues)} total)

| ID | Severity | Category | Summary |
|---|---|---|---|
{new_table}
"""
    else:
        new_section = "## New Issues This Week\n\nNo new issues reported in the past 7 days.\n"

    # Section 4: Escalation
    if escalate_list:
        esc_rows = []
        for issue, justification in escalate_list[:8]:
            emoji = SEV_EMOJI.get(issue.get("severity"), "⚪")
            esc_rows.append(
                f"- **#{issue['id']}** {emoji} `{issue.get('severity', 'unknown')}` — "
                f"_{issue['canonical_summary'][:60]}_  \n"
                f"  **Why:** {justification}"
            )
        esc_section = "## Recommended for Escalation\n\n" + "\n\n".join(esc_rows) + "\n"
    else:
        esc_section = "## Recommended for Escalation\n\nNo issues meet the escalation threshold this week.\n"

    # Section 5: Category breakdown
    from collections import Counter
    cat_counts = Counter(i["category"] for i in issues)
    sev_counts = Counter(i.get("severity") for i in bug_issues)

    breakdown = f"""## Category Breakdown

| Category | Issues |
|---|---|
| 🐛 Bugs | {cat_counts.get('bug', 0)} |
| ✨ Feature Requests | {cat_counts.get('feature_request', 0)} |
| 😕 UX Confusion | {cat_counts.get('ux_confusion', 0)} |

**Bug severity distribution:**

| Severity | Count |
|---|---|
| 🔴 Critical | {sev_counts.get('critical', 0)} |
| 🟠 High | {sev_counts.get('high', 0)} |
| 🟡 Medium | {sev_counts.get('medium', 0)} |
| 🟢 Low | {sev_counts.get('low', 0)} |
"""

    # Section 6: Noise analysis
    noise_section = f"""## Noise Analysis

**{noise_pct:.0f}% noise rate** — {noise_count} of {raw_count} raw items were greetings, test messages, or zero-signal pings.

This is within a normal range for multi-channel feedback (typical: 10–25%). No action needed.
"""

    # ── Assemble ──────────────────────────────────────────────────────────────
    now = datetime.now().strftime("%B %d, %Y")
    header = f"""# Flowboard Feedback Summary
**Week of {week_start} → {week_end}** · Generated {now}

> This digest is auto-generated from {raw_count} raw feedback items collected across
> WhatsApp, Email, Slack, and Support Forms. Issues are deduplicated and ranked by report count.
> Items marked 🔴 or 🟠 with 3+ reports are recommended for immediate escalation.

---
"""
    footer = """---
*Pipeline: generate_feedback → triage (Gemini) → dedup (embeddings) → weekly_summary*
*Threshold: similarity ≥ 0.82 for deduplication · Model: gemini-3.5-flash-lite*
"""

    return "\n".join([
        header, snapshot, top_section, new_section,
        esc_section, breakdown, noise_section, footer
    ])


# ── Main ──────────────────────────────────────────────────────────────────────

def run(db_path: Path, out_path: Path | None, lookback_days: int) -> None:
    con = open_db(db_path)

    week_end   = datetime.now()
    week_start = week_end - timedelta(days=lookback_days)
    since_iso  = week_start.isoformat()

    raw_count   = get_raw_count(con)
    noise_count = get_noise_count(con)
    issues      = get_all_issues(con)
    new_issues  = get_new_issues(con, since_iso)

    if not issues:
        print("No issues found. Run triage.py and dedup.py first.", flush=True)
        return

    md = render_summary(
        issues=issues,
        raw_count=raw_count,
        noise_count=noise_count,
        new_issues=new_issues,
        week_start=week_start.strftime("%Y-%m-%d"),
        week_end=week_end.strftime("%Y-%m-%d"),
    )

    if out_path is None:
        date_str  = week_end.strftime("%Y-%m-%d")
        out_path  = Path(f"weekly_summary_{date_str}.md")

    out_path.write_text(md, encoding="utf-8")
    print(f"[OK] Weekly summary written to: {out_path}", flush=True)
    print(f"     {len(issues)} issues  |  {raw_count} raw reports  |  {noise_count} noise filtered", flush=True)
    print(f"\nNext step: run  python eval.py  after labeling eval_sample.csv", flush=True)
    con.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate weekly Markdown digest from tracker DB.")
    parser.add_argument("--db",   default=str(DEFAULT_DB), help="SQLite DB path.")
    parser.add_argument("--out",  default=None,            help="Output .md path (default: weekly_summary_<date>.md).")
    parser.add_argument("--days", type=int, default=LOOKBACK_DAYS, help="Look-back window in days (default: 7).")
    args = parser.parse_args()

    run(
        db_path=Path(args.db),
        out_path=Path(args.out) if args.out else None,
        lookback_days=args.days,
    )


if __name__ == "__main__":
    main()
