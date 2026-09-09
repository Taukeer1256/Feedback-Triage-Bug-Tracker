"""
generate_bug_report.py
======================
For every issue classified as "bug" in the tracker, generates a developer-ready
Markdown bug report and saves it to the bug_reports/ directory.

Each report includes:
  - Title, severity, frequency, report count
  - Repro steps inferred from raw reports (flagged as "inferred" where unclear)
  - Supporting user quotes (verbatim, channel-attributed)
  - Canonical summary and first/last reported dates

JUDGMENT CALLS flagged with (J):

  (J) REPRO STEP INFERENCE: Steps are inferred by the LLM from raw user reports.
      Any step that can't be directly grounded in a user quote is flagged with
      "[INFERRED — needs confirmation]" so devs know what to verify first.

  (J) QUOTE SELECTION: At most 4 quotes per report to keep reports scannable.
      Quotes are picked to maximise channel diversity and wording variation,
      which helps devs understand the full surface area of the bug.

  (J) ONE FILE PER ISSUE: Rather than a master bug list, each issue gets its own
      .md file named bug_<issue_id>_<slug>.md. This makes it easy to link
      individual bugs in GitHub Issues, Jira, or Linear.

Usage:
    python generate_bug_report.py              # all bugs
    python generate_bug_report.py --id 7       # single issue
    python generate_bug_report.py --out reports/  # custom output dir
    python generate_bug_report.py --db tracker.db
"""

import argparse
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_DB      = Path("tracker.db")
DEFAULT_OUT_DIR = Path("bug_reports")
GEMINI_MODEL    = "gemini-3.5-flash-lite"
REQUEST_DELAY   = 2.0   # seconds between LLM calls

# ── DB helpers ────────────────────────────────────────────────────────────────

def open_db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def get_bug_issues(con: sqlite3.Connection, issue_id: int | None) -> list[dict]:
    if issue_id:
        rows = con.execute(
            "SELECT * FROM issues WHERE id = ? AND category = 'bug'", (issue_id,)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM issues WHERE category = 'bug' ORDER BY report_count DESC, severity DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_raw_reports(con: sqlite3.Connection, issue_id: int) -> list[dict]:
    rows = con.execute(
        """SELECT rr.source, rr.raw_text, rr.user_id, rr.timestamp
           FROM raw_reports rr
           WHERE rr.issue_id = ?
           ORDER BY rr.timestamp ASC""",
        (issue_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── LLM: infer repro steps ────────────────────────────────────────────────────

REPRO_PROMPT = """You are a developer writing a bug report for a SaaS app called Flowboard.

Given the user reports below for a single bug, infer the likely reproduction steps a developer would follow to reproduce the bug.

Rules:
- List 3-5 numbered steps.
- Each step that is DIRECTLY supported by user text should be written plainly.
- Each step that is INFERRED (not explicitly stated) must end with: [INFERRED — needs confirmation]
- Be concrete: include specific UI elements, button names, page names mentioned by users.
- Do NOT add steps that aren't at all supported by the reports.
- Return ONLY the numbered list, no intro text, no markdown headers.

Bug summary: {summary}

User reports:
{reports}"""


def infer_repro_steps(client: genai.Client, issue: dict, reports: list[dict]) -> str:
    """Call LLM to infer repro steps. Returns markdown-formatted numbered list."""
    formatted_reports = "\n".join(
        f"[{r['source']}] {r['raw_text'][:300]}" for r in reports[:8]
    )
    prompt = REPRO_PROMPT.format(
        summary=issue["canonical_summary"],
        reports=formatted_reports,
    )

    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=400),
            )
            text = (resp.text or "").strip()
            if text:
                return text
            time.sleep(2)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 30 * (attempt + 1)
                print(f"  [RATE LIMIT] Waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                print(f"  [WARN] LLM error: {e}", flush=True)
                time.sleep(2)

    return "1. [INFERRED — needs confirmation] Steps could not be inferred from available reports."


# ── Report renderer ───────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().replace(" ", "_")
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text[:50]


def pick_quotes(reports: list[dict], max_quotes: int = 4) -> list[dict]:
    """
    Select up to max_quotes reports, maximising channel diversity.
    (J) Prefer shorter quotes that are still specific — walls of text don't help devs.
    """
    # Sort by channel diversity first, then by specificity (longer = more specific)
    seen_channels: set[str] = set()
    picked: list[dict] = []
    remaining: list[dict] = []

    for r in reports:
        if r["source"] not in seen_channels and len(picked) < max_quotes:
            picked.append(r)
            seen_channels.add(r["source"])
        else:
            remaining.append(r)

    # Fill remaining slots
    for r in remaining:
        if len(picked) >= max_quotes:
            break
        picked.append(r)

    return picked


def render_report(issue: dict, reports: list[dict], repro_steps: str) -> str:
    """Render a Markdown bug report."""
    sev   = (issue["severity"]  or "unknown").upper()
    freq  = issue["frequency"]  or "unknown"
    count = issue["report_count"]
    first = issue["first_reported"][:10]
    last  = issue["last_reported"][:10]

    sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "⚪")

    quotes = pick_quotes(reports)
    quote_block = "\n\n".join(
        f"> **[{r['source']}]** — *{r['timestamp'][:10]}*\n> \"{r['raw_text'][:400]}\""
        for r in quotes
    )

    sources_summary = ", ".join(
        f"{src} ({sum(1 for r in reports if r['source'] == src)})"
        for src in sorted({r["source"] for r in reports})
    )

    return f"""# Bug Report: {issue['canonical_summary']}

**Issue ID:** #{issue['id']}
**Severity:** {sev_emoji} {sev}
**Frequency:** {freq.title()}
**Status:** {issue['status'].upper()}
**Report Count:** {count} reports from {len(reports)} raw entries
**Sources:** {sources_summary}
**First Reported:** {first}
**Last Reported:** {last}

---

## Summary

{issue['canonical_summary']}

---

## Reproduction Steps

> ⚠️ Steps marked **[INFERRED — needs confirmation]** are inferred from user descriptions
> and have not been directly verified. Confirm before closing as reproduced.

{repro_steps}

---

## Supporting User Reports

{quote_block}

---

## Metadata

| Field | Value |
|---|---|
| Category | Bug |
| Severity | {sev} |
| Frequency | {freq.title()} |
| Total Reports | {count} |
| Channels Affected | {sources_summary} |
| First Reported | {first} |
| Last Reported | {last} |

---

*Generated by Flowboard Feedback Triage Pipeline · Issue #{issue['id']}*
*Repro steps are inferred from user reports and should be verified before filing.*
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def run(db_path: Path, out_dir: Path, issue_id: int | None) -> None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set in .env")
    client = genai.Client(api_key=api_key)

    con     = open_db(db_path)
    issues  = get_bug_issues(con, issue_id)

    if not issues:
        print("No bug issues found. Check DB or --id value.", flush=True)
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nGenerating bug reports for {len(issues)} bugs -> {out_dir}/\n", flush=True)

    generated = []
    for i, issue in enumerate(issues, 1):
        print(f"[{i:>2}/{len(issues)}] #{issue['id']} sev={issue['severity']} | {issue['canonical_summary'][:60]}...", flush=True)

        reports = get_raw_reports(con, issue["id"])
        if not reports:
            print(f"  [SKIP] No raw reports linked — skipping.", flush=True)
            continue

        print(f"  Inferring repro steps from {len(reports)} reports...", flush=True)
        repro_steps = infer_repro_steps(client, issue, reports)

        md_content = render_report(issue, reports, repro_steps)

        slug     = slugify(issue["canonical_summary"])
        filename = f"bug_{issue['id']:03d}_{slug}.md"
        filepath = out_dir / filename
        filepath.write_text(md_content, encoding="utf-8")

        print(f"  Saved: {filepath}", flush=True)
        generated.append(filepath)
        time.sleep(REQUEST_DELAY)

    print(f"\n{'='*55}", flush=True)
    print(f"BUG REPORTS COMPLETE", flush=True)
    print(f"{'='*55}", flush=True)
    print(f"  Generated : {len(generated)} reports", flush=True)
    print(f"  Output dir: {out_dir.resolve()}", flush=True)
    print(f"\nNext step: run  python weekly_summary.py", flush=True)
    con.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Markdown bug reports from triaged issues.")
    parser.add_argument("--db",  default=str(DEFAULT_DB),      help="SQLite DB path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="Output directory for .md files.")
    parser.add_argument("--id",  type=int, default=None,        help="Generate report for a single issue ID.")
    args = parser.parse_args()

    run(
        db_path=Path(args.db),
        out_dir=Path(args.out),
        issue_id=args.id,
    )


if __name__ == "__main__":
    main()
