"""
run_pipeline.py
===============
Single entry-point to run the entire Feedback Triage & Bug Tracker pipeline
end-to-end. Run this after adding GOOGLE_API_KEY to .env.

Steps:
  1. generate_feedback  — create synthetic data (feedback_raw.csv)
  2. triage             — LLM classification into DB
  3. dedup              — embedding-based deduplication
  4. generate_bug_report— Markdown bug reports per bug issue
  5. weekly_summary     — founder-ready weekly digest
  6. eval --export      — export sample CSV for hand-labeling

Usage:
    python run_pipeline.py                 # full run from scratch
    python run_pipeline.py --skip-generate # reuse existing feedback_raw.csv
    python run_pipeline.py --resume        # resume triage if it crashed midway
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)


def run_step(name: str, cmd: list[str], cwd: Path) -> bool:
    """Run a pipeline step, print its output, return True on success."""
    sep = "=" * 58
    print(f"\n{sep}", flush=True)
    print(f"  STEP: {name}", flush=True)
    print(f"  CMD : {' '.join(cmd)}", flush=True)
    print(f"{sep}\n", flush=True)

    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        # Inherit stdout/stderr so output streams live to the terminal
        stdout=None,
        stderr=None,
    )

    if result.returncode != 0:
        print(f"\n[FAILED] Step '{name}' exited with code {result.returncode}.", flush=True)
        print(f"Fix the error above and re-run with --resume if triage was mid-way.", flush=True)
        return False

    print(f"\n[OK] Step '{name}' completed.", flush=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full feedback triage pipeline.")
    parser.add_argument("--skip-generate", action="store_true",
                        help="Skip data generation step (reuse existing feedback_raw.csv).")
    parser.add_argument("--resume", action="store_true",
                        help="Resume triage from where it left off (don't --reset DB).")
    parser.add_argument("--dry-dedup", action="store_true",
                        help="Run dedup in --dry-run mode (no DB writes).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for data generation (default: 42).")
    args = parser.parse_args()

    cwd    = Path(__file__).parent
    py     = sys.executable   # same Python that launched this script
    start  = time.time()

    steps_run = 0
    steps_ok  = 0

    # ── Step 1: Generate synthetic data ──────────────────────────────────────
    if not args.skip_generate:
        ok = run_step(
            "Generate synthetic feedback data",
            [py, "generate_feedback.py", "--seed", str(args.seed)],
            cwd,
        )
        steps_run += 1
        if ok:
            steps_ok += 1
        else:
            sys.exit(1)
    else:
        print("[SKIP] Data generation skipped — using existing feedback_raw.csv", flush=True)

    # ── Step 2: Triage ───────────────────────────────────────────────────────
    triage_cmd = [py, "-u", "triage.py"]
    if not args.resume:
        triage_cmd.append("--reset")   # fresh run wipes old triage data

    ok = run_step("Triage with Gemini LLM", triage_cmd, cwd)
    steps_run += 1
    if ok:
        steps_ok += 1
    else:
        print("[HINT] If triage crashed partway, re-run with --resume to continue.", flush=True)
        sys.exit(1)

    # ── Step 3: Dedup ────────────────────────────────────────────────────────
    dedup_cmd = [py, "-u", "dedup.py"]
    if args.dry_dedup:
        dedup_cmd.append("--dry-run")

    ok = run_step("Deduplicate with embeddings", dedup_cmd, cwd)
    steps_run += 1
    if ok:
        steps_ok += 1
    else:
        sys.exit(1)

    # ── Step 4: Bug reports ───────────────────────────────────────────────────
    ok = run_step(
        "Generate Markdown bug reports",
        [py, "-u", "generate_bug_report.py"],
        cwd,
    )
    steps_run += 1
    if ok:
        steps_ok += 1
    else:
        sys.exit(1)

    # ── Step 5: Weekly summary ────────────────────────────────────────────────
    ok = run_step(
        "Generate weekly summary",
        [py, "-u", "weekly_summary.py"],
        cwd,
    )
    steps_run += 1
    if ok:
        steps_ok += 1
    else:
        sys.exit(1)

    # ── Step 6: Export eval sample ────────────────────────────────────────────
    ok = run_step(
        "Export evaluation sample for hand-labeling",
        [py, "-u", "eval.py", "--export"],
        cwd,
    )
    steps_run += 1
    if ok:
        steps_ok += 1

    # ── Final summary ─────────────────────────────────────────────────────────
    elapsed = time.time() - start
    print(f"\n{'=' * 58}", flush=True)
    print(f"  PIPELINE COMPLETE — {steps_ok}/{steps_run} steps succeeded", flush=True)
    print(f"  Total time: {elapsed / 60:.1f} min", flush=True)
    print(f"{'=' * 58}", flush=True)
    print(f"\nOutputs:", flush=True)
    print(f"  feedback_raw.csv          — raw synthetic data", flush=True)
    print(f"  tracker.db                — SQLite issue tracker", flush=True)
    print(f"  bug_reports/              — one .md file per bug", flush=True)
    print(f"  weekly_summary_<date>.md  — founder digest", flush=True)
    print(f"  eval_sample.csv           — label this, then run: python eval.py", flush=True)


if __name__ == "__main__":
    main()
