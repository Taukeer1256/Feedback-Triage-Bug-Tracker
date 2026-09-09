"""
triage.py
=========
Classifies each raw feedback item using the Gemini API (gemini-3.6-flash).

For each item it produces:
  - category         : bug | feature_request | ux_confusion | duplicate | noise
  - confidence       : 0.0-1.0 float
  - rationale        : one-line string
  - severity         : low | medium | high | critical | null  (bugs only)
  - frequency        : isolated | recurring | null            (bugs only)
  - canonical_summary: short clean summary of the issue

Results are written into SQLite (raw_reports + issues tables).

JUDGMENT CALLS flagged with (J):

  (J) MODEL: gemini-3.6-flash — fastest free-tier model with JSON output support.
      Switch to gemini-3.7-flash or gemini-3.8-flash for higher accuracy.

  (J) SDK: Uses the newer `google-genai` REST-based SDK (not `google-generativeai`
      gRPC SDK) because it is more reliable on Windows and doesn't hang on init.

  (J) BATCH SIZE: Items are sent one-at-a-time (not batched) so individual
      failures can be retried without re-spending quota.

  (J) SEVERITY HEURISTICS: Severity is inferred by the LLM using explicit
      criteria in the prompt (data loss = critical, auth broken = high,
      cosmetic = low) for consistency.

  (J) DUPLICATE vs SIMILAR: The triage step marks "duplicate" only when the
      *same user* reports the same thing twice. Cross-user near-duplicates are
      handled by dedup.py (embedding-based).

Usage:
    python triage.py                  # processes all rows in feedback_raw.csv
    python triage.py --limit 5        # quick test on first 5 rows
    python triage.py --reset          # wipe existing triage results and re-run
    python triage.py --db tracker.db  # override DB path
"""

import argparse
import csv
import json
import os
import sqlite3
import time
from collections import Counter
from pathlib import Path

import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Force unbuffered utf-8 output — avoids cp1252 crashes on emoji in raw text
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_MODEL      = "gemini-3.5-flash-lite"
INPUT_CSV         = Path("feedback_raw.csv")
SCHEMA_SQL        = Path("schema.sql")
DEFAULT_DB        = Path("tracker.db")
REQUEST_DELAY_SEC = 1.0   # (J) increase to 4.0 if you hit 429 rate-limit errors

# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a product-ops analyst triaging user feedback for a SaaS app called Flowboard.

Classify each feedback message into EXACTLY ONE category and return structured JSON.

CATEGORIES:
- bug            : Something is broken, crashing, not working as intended, or data is lost/corrupted.
- feature_request: User is asking for new functionality that does not exist yet.
- ux_confusion   : Product works as designed but user is confused or can't find something. NOT a bug.
- duplicate      : This exact same user already reported the same issue (rare — use sparingly).
- noise          : Greetings, tests, accidental sends, empty pings, zero actionable content.

SEVERITY — set only for bugs, null for everything else:
- critical : Data loss, authentication completely broken, app entirely unusable.
- high     : Core feature broken, no obvious workaround.
- medium   : Feature degraded but workaround exists, or minor feature affected.
- low      : Cosmetic issue, minor annoyance, very edge-case.

FREQUENCY — set only for bugs, null for everything else:
- recurring : User says it happens every time / always / repeatedly, or pattern is clear.
- isolated  : Happened once or rarely, unclear pattern.

CANONICAL SUMMARY — for all non-noise items:
One clean sentence (max 12 words) capturing the core issue or request.
For noise items write: N/A

Return ONLY valid JSON with this exact schema — no markdown, no explanation:
{
  "category": "<category>",
  "confidence": <float 0.0-1.0>,
  "rationale": "<one sentence explaining classification>",
  "severity": "<severity or null>",
  "frequency": "<frequency or null>",
  "canonical_summary": "<summary>"
}"""

# ── DB helpers ────────────────────────────────────────────────────────────────

def init_db(db_path: Path) -> sqlite3.Connection:
    """Open (or create) the SQLite DB and apply the schema."""
    schema = SCHEMA_SQL.read_text(encoding="utf-8")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript(schema)
    con.commit()
    return con


def insert_raw_report(con: sqlite3.Connection, row: dict, triage: dict) -> int:
    """Insert a raw_reports row and return its rowid."""
    cur = con.execute(
        """INSERT INTO raw_reports
           (source, raw_text, user_id, timestamp, triage_category, triage_confidence, triage_rationale)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            row["source"],
            row["raw_text"],
            row["user_id"],
            row["timestamp"],
            triage.get("category"),
            triage.get("confidence"),
            triage.get("rationale"),
        ),
    )
    con.commit()
    return cur.lastrowid


def upsert_issue(con: sqlite3.Connection, row: dict, triage: dict, report_id: int) -> int | None:
    """
    Create a new issue row for every non-noise item and link the raw_report to it.
    dedup.py will later merge these into clusters and update report_count.
    Returns the new issue id, or None for noise.
    """
    category = triage["category"]
    if category == "noise":
        return None

    severity  = triage.get("severity")
    frequency = triage.get("frequency")

    cur = con.execute(
        """INSERT INTO issues
           (category, severity, frequency, status,
            first_reported, last_reported, report_count, canonical_summary)
           VALUES (?, ?, ?, 'open', ?, ?, 1, ?)""",
        (
            category,
            severity if severity not in (None, "null") else None,
            frequency if frequency not in (None, "null") else None,
            row["timestamp"],
            row["timestamp"],
            triage.get("canonical_summary", ""),
        ),
    )
    issue_id = cur.lastrowid
    con.execute("UPDATE raw_reports SET issue_id = ? WHERE id = ?", (issue_id, report_id))
    con.commit()
    return issue_id


# ── Gemini call ───────────────────────────────────────────────────────────────

VALID_CATEGORIES  = {"bug", "feature_request", "ux_confusion", "duplicate", "noise"}
VALID_SEVERITIES  = {"low", "medium", "high", "critical"}
VALID_FREQUENCIES = {"isolated", "recurring"}


def validate_and_clean(raw: dict) -> dict:
    """Normalise and validate the LLM JSON response."""
    cat = str(raw.get("category", "noise")).lower().strip()
    if cat not in VALID_CATEGORIES:
        cat = "noise"

    severity  = raw.get("severity")
    frequency = raw.get("frequency")

    # Normalise null variants
    severity  = None if str(severity).lower()  in ("none", "null", "n/a", "") else str(severity).lower().strip()
    frequency = None if str(frequency).lower() in ("none", "null", "n/a", "") else str(frequency).lower().strip()

    # Non-bugs must not carry severity/frequency
    if cat != "bug":
        severity  = None
        frequency = None

    # Clamp values to allowed sets
    if severity  not in VALID_SEVERITIES:  severity  = None
    if frequency not in VALID_FREQUENCIES: frequency = None

    confidence = float(raw.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))

    return {
        "category":          cat,
        "confidence":        confidence,
        "rationale":         str(raw.get("rationale", ""))[:500],
        "severity":          severity,
        "frequency":         frequency,
        "canonical_summary": str(raw.get("canonical_summary", ""))[:200],
    }


# JSON schema enforced in prompt as a reliable fallback
_JSON_EXAMPLE = '''
Return ONLY this JSON, no markdown, no extra text:
{
  "category": "noise",
  "confidence": 0.99,
  "rationale": "one sentence",
  "severity": null,
  "frequency": null,
  "canonical_summary": "N/A"
}'''


def call_gemini(client: genai.Client, source: str, text: str, retries: int = 3) -> dict:
    """Call Gemini and return a validated triage dict.

    Uses plain text mode (not response_mime_type) to avoid empty-response
    issues on very short inputs. JSON is enforced via explicit prompt schema.
    """
    full_prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"Example output format:{_JSON_EXAMPLE}\n\n"
        f"Now classify this feedback from a {source} message:\n"
        f'"""{text[:2000]}"""'
    )

    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=300,
                ),
            )

            # Guard: response.text can be None for empty/blocked responses
            raw_text = (response.text or "").strip()
            if not raw_text:
                print(f"  [WARN] Empty response on attempt {attempt}/{retries}, retrying...")
                time.sleep(2)
                continue

            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                parts = raw_text.split("```")
                raw_text = parts[1].lstrip("json").strip() if len(parts) > 1 else raw_text

            # Extract first JSON object if there's extra text around it
            start = raw_text.find("{")
            end   = raw_text.rfind("}") + 1
            if start != -1 and end > start:
                raw_text = raw_text[start:end]

            return validate_and_clean(json.loads(raw_text))

        except json.JSONDecodeError as e:
            print(f"  [WARN] JSON parse error attempt {attempt}/{retries}: {e}", flush=True)
            print(f"  Raw: {(response.text or '')[:120]}", flush=True)
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = 30 * attempt
                print(f"  [RATE LIMIT] Waiting {wait}s (attempt {attempt}/{retries})...", flush=True)
                time.sleep(wait)
            else:
                print(f"  [ERROR] attempt {attempt}/{retries}: {e}", flush=True)
                if attempt == retries:
                    break
                time.sleep(2)

    # Safe fallback after all retries
    return validate_and_clean({
        "category": "noise", "confidence": 0.0,
        "rationale": "Triage failed after retries — marked as noise.",
        "severity": None, "frequency": None, "canonical_summary": "N/A",
    })


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_triage(input_csv: Path, db_path: Path, limit: int | None, reset: bool) -> None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not found in .env")

    client = genai.Client(api_key=api_key)
    con    = init_db(db_path)

    if reset:
        print("[RESET] Clearing existing triage data...", flush=True)
        con.executescript("DELETE FROM raw_reports; DELETE FROM issues;")
        con.commit()

    with input_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # --resume: skip rows already written to DB (crash recovery)
    already_done = con.execute("SELECT COUNT(*) FROM raw_reports").fetchone()[0]
    if already_done > 0 and not reset:
        print(f"[RESUME] {already_done} rows already in DB — skipping them.", flush=True)
        rows = rows[already_done:]

    if limit:
        rows = rows[:limit]

    total = len(rows)
    est_min = total * REQUEST_DELAY_SEC / 60
    print(f"\nTriaging {total} items using {GEMINI_MODEL}", flush=True)
    print(f"Estimated time: ~{est_min:.1f} min at {REQUEST_DELAY_SEC}s/request\n", flush=True)

    cat_counts = Counter()
    errors     = 0

    for i, row in enumerate(rows, 1):
        # Sanitize preview: replace non-ASCII chars to avoid cp1252 crash
        preview = row["raw_text"][:60].replace("\n", " ").encode("ascii", errors="replace").decode("ascii")
        print(f"[{i:>3}/{total}] {row['source']:<13} | {preview}...", flush=True)

        try:
            triage = call_gemini(client, row["source"], row["raw_text"])
        except Exception as e:
            print(f"         [FAIL] {e}")
            errors += 1
            continue

        report_id = insert_raw_report(con, row, triage)
        upsert_issue(con, row, triage, report_id)
        cat_counts[triage["category"]] += 1

        sev_tag = f" sev={triage['severity']}" if triage["severity"] else ""
        print(f"         -> {triage['category']:<17} conf={triage['confidence']:.2f}{sev_tag}", flush=True)

        time.sleep(REQUEST_DELAY_SEC)

    # ── Final summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 58)
    print("TRIAGE COMPLETE")
    print("=" * 58)
    print(f"  Processed : {total}  |  Errors: {errors}  |  Written: {total - errors}")
    print("\nCategory breakdown:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:<20} {count:>3}  {'|' * count}")

    rr = con.execute("SELECT COUNT(*) FROM raw_reports").fetchone()[0]
    is_ = con.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    print(f"\nDB: {rr} raw_reports | {is_} issues")
    print("\nNext step: run  python dedup.py")
    con.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Triage feedback with Gemini.")
    parser.add_argument("--input",  default=str(INPUT_CSV))
    parser.add_argument("--db",     default=str(DEFAULT_DB))
    parser.add_argument("--limit",  type=int, default=None, help="Process only first N rows.")
    parser.add_argument("--reset",  action="store_true",    help="Wipe DB and re-run.")
    args = parser.parse_args()

    run_triage(
        input_csv=Path(args.input),
        db_path=Path(args.db),
        limit=args.limit,
        reset=args.reset,
    )


if __name__ == "__main__":
    main()
