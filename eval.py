"""
eval.py
=======
Compares the pipeline's triage classifications against your hand-labels and
reports precision, recall, and F1 per category.

Workflow:
  1. Run: python eval.py --export          -> writes eval_sample.csv (30 random rows)
  2. Open eval_sample.csv and fill in the  'true_label' column yourself
  3. Run: python eval.py                   -> reads eval_sample.csv, prints metrics

The metrics printed here are what you cite in your resume/interview. The script
is designed to be re-runnable: edit eval_sample.csv and re-run anytime.

JUDGMENT CALLS flagged with (J):

  (J) SAMPLE SIZE: 30 items, stratified by category_hint to ensure at least
      one item from each category is represented. Purely random sampling of 30
      from 180 could miss rare categories entirely.

  (J) METRIC: We report per-category precision, recall, F1, and macro-average.
      Macro-average (unweighted mean across categories) is the right choice here
      because categories are imbalanced — we don't want noise (35 items) to
      dominate the aggregate score.

Usage:
    python eval.py --export              # create eval_sample.csv for labeling
    python eval.py                       # run evaluation against your labels
    python eval.py --sample eval_sample.csv  # custom file path
"""

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

DEFAULT_DB     = Path("tracker.db")
SAMPLE_FILE    = Path("eval_sample.csv")
SAMPLE_SIZE    = 30
CATEGORIES     = ["bug", "feature_request", "ux_confusion", "noise"]
# Note: "duplicate" is excluded from eval because it's nearly absent after dedup


# ── Export: create the sample CSV for hand-labeling ──────────────────────────

def export_sample(db_path: Path, sample_file: Path, n: int = SAMPLE_SIZE) -> None:
    """
    Pull n rows from raw_reports stratified by triage_category,
    write to CSV with an empty true_label column for you to fill in.
    """
    import random
    random.seed(42)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # Stratified sample: pull from each category proportionally
    all_rows: list[dict] = []
    cats = ["bug", "feature_request", "ux_confusion", "noise"]
    per_cat = (n // len(cats)) + 2

    for cat in cats:
        rows = con.execute(
            "SELECT id, source, raw_text, user_id, timestamp, triage_category "
            "FROM raw_reports WHERE triage_category = ? ORDER BY RANDOM() LIMIT ?",
            (cat, per_cat)
        ).fetchall()
        all_rows.extend(dict(r) for r in rows)

    # Trim to exactly n
    random.shuffle(all_rows)
    all_rows = all_rows[:n]
    con.close()

    fieldnames = ["raw_report_id", "source", "timestamp", "raw_text",
                  "pipeline_label", "true_label", "notes"]

    with sample_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_rows:
            writer.writerow({
                "raw_report_id":  r["id"],
                "source":         r["source"],
                "timestamp":      r["timestamp"],
                "raw_text":       r["raw_text"],
                "pipeline_label": r["triage_category"],
                "true_label":     "",    # <-- YOU FILL THIS IN
                "notes":          "",    # optional comments
            })

    print(f"[OK] Exported {len(all_rows)} items to {sample_file}", flush=True)
    print(f"\nInstructions:", flush=True)
    print(f"  1. Open {sample_file} in Excel or any spreadsheet editor.", flush=True)
    print(f"  2. For each row, fill in the 'true_label' column with ONE of:", flush=True)
    print(f"       bug | feature_request | ux_confusion | noise | duplicate", flush=True)
    print(f"  3. Save the file and run: python eval.py", flush=True)


# ── Evaluate: compute precision/recall/F1 ────────────────────────────────────

def evaluate(sample_file: Path) -> None:
    """Load hand-labeled CSV and compute per-category + macro metrics."""
    if not sample_file.exists():
        print(f"[ERROR] {sample_file} not found. Run: python eval.py --export first.", flush=True)
        return

    rows = []
    with sample_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            pl = (r.get("pipeline_label") or "").strip().lower()
            tl = (r.get("true_label")     or "").strip().lower()
            if not tl:
                continue   # skip unlabeled rows
            rows.append({"predicted": pl, "true": tl})

    if not rows:
        print("[ERROR] No labeled rows found in true_label column. Fill it in first.", flush=True)
        return

    n = len(rows)
    print(f"\nEvaluating {n} labeled items...\n", flush=True)

    # Confusion matrix
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)

    for r in rows:
        pred = r["predicted"]
        true = r["true"]
        if pred == true:
            tp[true] += 1
        else:
            fp[pred] += 1
            fn[true] += 1

    # Per-category metrics
    all_cats = sorted({r["true"] for r in rows} | {r["predicted"] for r in rows})
    results  = {}

    for cat in all_cats:
        p_denom = tp[cat] + fp[cat]
        r_denom = tp[cat] + fn[cat]
        precision = tp[cat] / p_denom if p_denom else 0.0
        recall    = tp[cat] / r_denom if r_denom else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0.0)
        support   = sum(1 for r in rows if r["true"] == cat)
        results[cat] = {"precision": precision, "recall": recall,
                        "f1": f1, "support": support}

    # Macro averages (unweighted — (J) see module docstring)
    macro_p = sum(v["precision"] for v in results.values()) / len(results)
    macro_r = sum(v["recall"]    for v in results.values()) / len(results)
    macro_f = sum(v["f1"]        for v in results.values()) / len(results)

    # Overall accuracy
    correct = sum(1 for r in rows if r["predicted"] == r["true"])
    accuracy = correct / n

    # ── Print report ──────────────────────────────────────────────────────────
    print("=" * 62, flush=True)
    print("TRIAGE PIPELINE EVALUATION RESULTS", flush=True)
    print("=" * 62, flush=True)
    print(f"  Labeled items evaluated: {n}", flush=True)
    print(f"  Overall accuracy:        {accuracy:.1%}\n", flush=True)

    header = f"  {'Category':<20} {'Precision':>9} {'Recall':>9} {'F1':>9} {'Support':>8}"
    print(header, flush=True)
    print("  " + "-" * 58, flush=True)

    for cat in sorted(results.keys()):
        v = results[cat]
        print(f"  {cat:<20} {v['precision']:>9.1%} {v['recall']:>9.1%} "
              f"{v['f1']:>9.1%} {v['support']:>8}", flush=True)

    print("  " + "-" * 58, flush=True)
    print(f"  {'Macro average':<20} {macro_p:>9.1%} {macro_r:>9.1%} {macro_f:>9.1%}", flush=True)
    print("=" * 62, flush=True)

    # Resume-ready one-liner
    print(f"\nResume/interview cite:", flush=True)
    print(f"  \"Triage pipeline achieved {accuracy:.0%} accuracy and {macro_f:.0%} macro-F1 "
          f"across {len(all_cats)} categories on a {n}-item hand-labeled sample.\"", flush=True)

    # Write results to markdown for README
    _write_eval_md(results, macro_p, macro_r, macro_f, accuracy, n)


def _write_eval_md(results: dict, macro_p: float, macro_r: float,
                   macro_f: float, accuracy: float, n: int) -> None:
    """Write eval results as a markdown snippet for pasting into README."""
    rows = []
    for cat in sorted(results.keys()):
        v = results[cat]
        rows.append(
            f"| {cat:<20} | {v['precision']:.1%} | {v['recall']:.1%} | {v['f1']:.1%} | {v['support']} |"
        )
    table = "\n".join(rows)

    md = f"""## Evaluation Results

Evaluated on {n} hand-labeled items (stratified sample from `eval_sample.csv`).

| Category | Precision | Recall | F1 | Support |
|---|---|---|---|---|
{table}
| **Macro average** | **{macro_p:.1%}** | **{macro_r:.1%}** | **{macro_f:.1%}** | — |

**Overall accuracy: {accuracy:.1%}**

Model: `gemini-3.5-flash-lite` · Dedup threshold: `0.82`
"""
    out = Path("eval_results.md")
    out.write_text(md, encoding="utf-8")
    print(f"\n[OK] Results also saved to {out} (paste into README.md)", flush=True)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate triage pipeline against hand labels.")
    parser.add_argument("--export", action="store_true",
                        help="Export 30-item sample CSV for hand-labeling.")
    parser.add_argument("--sample", default=str(SAMPLE_FILE),
                        help=f"Sample CSV path (default: {SAMPLE_FILE}).")
    parser.add_argument("--db",     default=str(DEFAULT_DB),
                        help="SQLite DB path (used with --export).")
    args = parser.parse_args()

    if args.export:
        export_sample(Path(args.db), Path(args.sample))
    else:
        evaluate(Path(args.sample))


if __name__ == "__main__":
    main()
