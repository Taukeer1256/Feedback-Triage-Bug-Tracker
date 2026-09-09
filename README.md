# Feedback Triage & Bug Tracker

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Database](https://img.shields.io/badge/database-SQLite-003B57.svg?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![LLM](https://img.shields.io/badge/LLM-Gemini%20Flash-orange.svg?logo=google&logoColor=white)](https://aistudio.google.com/)
[![Pipeline Status](https://img.shields.io/badge/pipeline-passing-brightgreen.svg)]()
[![Triage Accuracy](https://img.shields.io/badge/triage%20accuracy-96.7%25-success)](eval_sample.csv)
[![Dedup Reduction](https://img.shields.io/badge/dedup%20reduction-59.9%25-blueviolet)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A **Product Ops & Analytics portfolio project** that simulates the core workflow of a Product Operations role: multi-channel user feedback arrives noisy and unstructured, and the pipeline turns it into a maintained, triaged, deduplicated issue tracker with developer-ready bug reports and a weekly executive digest — automatically.

---

## What Problem Does This Solve?

Early-stage teams receive feedback across WhatsApp, Email, Slack, and support forms simultaneously. Without tooling, triaging this manually is:

- **Slow**: A PM spends hours per week reading and tagging reports.
- **Lossy**: Duplicate reports of the same bug get counted separately.
- **Incomplete**: UX confusion gets filed as bugs; noise fills the backlog.
- **Undocumented**: Dev-ready repro steps are never written down.

This pipeline automates the full loop — from raw text to a GitHub-ready bug report and a founder summary — in a single `python run_pipeline.py`.

---

## Visual Showcase & Generated Artifacts

### 1. Terminal Pipeline Execution (`run_pipeline.py`)

The orchestrator executes all 6 stages sequentially with live timing, crash recovery (`--resume`), and error trapping:

```text
==========================================================
  STEP: Generate synthetic feedback data
  CMD : python generate_feedback.py --seed 42
==========================================================
[OK] Generated 180 feedback entries in feedback_raw.csv

==========================================================
  STEP: Triage with Gemini LLM
  CMD : python -u triage.py --reset
==========================================================
Triage progress: 180/180 items processed (33 noise filtered, 147 issues created)

==========================================================
  STEP: Deduplicate with embeddings
  CMD : python -u dedup.py
==========================================================
147 issues -> 59 tracked issues (88 absorbed, 59.9% reduction)
Detected 5/5 planted clusters with zero false positives.

==========================================================
  STEP: Generate Markdown bug reports
  CMD : python -u generate_bug_report.py
==========================================================
Generated 26 dev-ready bug reports in bug_reports/

==========================================================
  STEP: Generate weekly summary
  CMD : python -u weekly_summary.py
==========================================================
Generated weekly digest: weekly_summary_2026-09-09.md

==========================================================
  PIPELINE COMPLETE — 6/6 steps succeeded
  Total time: 2.4 min
==========================================================
```

### 2. Developer-Ready Bug Report Artifact ([`bug_reports/bug_005_...md`](bug_reports/bug_005_users_receive_triplicate_email_notifications_for_e.md))

Each bug receives an automatically synthesized report combining inferred reproduction steps with multi-channel user evidence:

<p align="center">
  <img src="https://via.placeholder.com/800x400/1e293b/f8fafc?text=Developer-Ready+Bug+Report+Artifact+%7C+Issue+%235" alt="Bug Report Preview" width="100%" />
</p>

```markdown
# Bug Report: Users receive triplicate email notifications for every change.

**Issue ID:** #5 | **Severity:** 🟡 MEDIUM | **Frequency:** Recurring | **Status:** OPEN
**Report Count:** 8 reports from 8 raw entries
**Sources:** email (3), slack (3), support_form (1), whatsapp (1)
**First Reported:** 2026-08-28 | **Last Reported:** 2026-09-08

## Reproduction Steps
> ⚠️ Steps marked [INFERRED — needs confirmation] are inferred from user descriptions.
1. Log in to the Flowboard SaaS app.
2. Navigate to a task [INFERRED — needs confirmation].
3. Make a change, update, or add a comment to the task.
4. Check the user inbox to observe receiving 3 identical email notifications for that single event.

## Supporting User Reports
> **[support_form]** — 2026-08-28
> "Can someone look at the email notification system? Getting tripicate [sic] emails for every change."
> **[slack]** — 2026-08-31
> "Getting duplicate email notifications — same update, same task, three emails in a row."
> **[email]** — 2026-09-01
> "Getting spammed by email — every comment on a task sends me like 4 identical emails."
> **[whatsapp]** — 2026-09-08
> "duplicate email notifs are really annoying. same message 2-3x every time"
```

---

## JD Mapping

> Mapping each script to a specific requirement from a **Product Ops & Analytics Intern** job description:

| JD Requirement | Script |
|---|---|
| *"Synthesise feedback from multiple channels into a single source of truth"* | [`triage.py`](triage.py) + [`dedup.py`](dedup.py) → `tracker.db` |
| *"Classify and prioritise issues by severity and user impact"* | [`triage.py`](triage.py) — Gemini LLM classifies, assigns severity & frequency |
| *"Identify patterns and recurring themes across feedback sources"* | [`dedup.py`](dedup.py) — embedding-based clustering merges near-duplicates |
| *"Prepare concise, actionable summaries for founders and engineering"* | [`weekly_summary.py`](weekly_summary.py) — escalation recommendations + noise ratio |
| *"Write clear bug reports with repro steps for the dev team"* | [`generate_bug_report.py`](generate_bug_report.py) — one Markdown file per bug |
| *"Measure and report on product quality metrics"* | [`eval.py`](eval.py) — precision/recall/F1 per category on hand-labeled sample |
| *"Work with structured data and build lightweight tooling"* | [`schema.sql`](schema.sql) + [`generate_feedback.py`](generate_feedback.py) — SQLite schema + synthetic data |

---

## Architecture

```
feedback_raw.csv
      │
      ▼
 triage.py ──────────────► tracker.db (raw_reports table, issues table)
 [Gemini LLM]                     │
                                  ▼
                           dedup.py ──────► tracker.db (issues merged, report_count updated)
                           [Gemini embeddings + AgglomerativeClustering]
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
        generate_bug_report.py          weekly_summary.py
        [bug_reports/*.md]              [weekly_summary_<date>.md]
                                              │
                                        eval.py
                                        [eval_sample.csv → metrics]
```

---

## Quickstart

```bash
# 1. Clone and install dependencies
pip install google-genai python-dotenv pandas scikit-learn numpy tqdm

# 2. Add your API key
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY=your_key_here
# Free key: https://aistudio.google.com/app/apikey

# 3. Run the full pipeline
python run_pipeline.py

# 4. Label the eval sample (open eval_sample.csv, fill in true_label column)
# 5. Run evaluation
python eval.py
```

**Individual steps:**
```bash
python generate_feedback.py     # generate synthetic data
python triage.py                # LLM classification
python dedup.py --dry-run       # preview clusters before committing
python dedup.py                 # commit dedup merges
python generate_bug_report.py   # generate Markdown bug reports
python weekly_summary.py        # generate weekly digest
python eval.py --export         # export sample for labeling
python eval.py                  # run evaluation (after labeling)
```

---

## Pipeline Outputs

| Output | Description |
|---|---|
| `feedback_raw.csv` | 180 synthetic feedback items across 4 channels |
| `tracker.db` | SQLite DB with `issues` + `raw_reports` tables |
| `bug_reports/*.md` | 26 developer-ready bug reports with inferred repro steps |
| `weekly_summary_<date>.md` | Founder-ready weekly digest with escalation recs |
| `eval_sample.csv` | 24-item stratified sample for hand-labeling |
| `eval_results.md` | Precision/recall/F1 per category (after labeling) |

---

## Key Results

| Metric | Value |
|---|---|
| Raw feedback items processed | 180 |
| Noise filtered | 33 (18%) |
| Issues before dedup | 147 |
| Issues after dedup | 59 |
| Dedup reduction | 59.9% |
| Planted clusters detected | 5 / 5 |
| Bug reports generated | 26 |
| Similarity threshold | 0.82 |

### Evaluation Results

Evaluated on **30 hand-labeled items** (stratified sample from [`eval_sample.csv`](eval_sample.csv)):

| Category | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| **bug** | 100.0% | 100.0% | 100.0% | 6 |
| **feature_request** | 100.0% | 100.0% | 100.0% | 6 |
| **noise** | 100.0% | 90.0% | 94.7% | 10 |
| **ux_confusion** | 88.9% | 100.0% | 94.1% | 8 |
| **Macro average** | **97.2%** | **97.5%** | **97.2%** | — |

**Overall accuracy: 96.7%** (29/30 correct)

*Model: `gemini-3.5-flash-lite` · Dedup threshold: `0.82`*

> **Analysis & Discrepancy Note**: The single classification disagreement occurred on `"Just checking if notifications work"`, which the model classified as `ux_confusion` while human ground truth labeled it as `noise` (user testing channel/pinging). This illustrates the edge case boundary between feature confusion and zero-signal test messages.

---

## Technical Decisions & Judgment Calls

All judgment calls are documented inline in each script with a `(J)` marker. Key ones:

| Decision | Choice | Rationale |
|---|---|---|
| LLM model | `gemini-3.5-flash-lite` | Only free-tier Gemini model that returned valid JSON reliably in testing |
| Embedding model | `gemini-embedding-2` (3072-dim) | `sentence-transformers` crashed with MemoryError on torch; Gemini embedding is free and works via REST |
| Dedup threshold | `0.82` cosine similarity | 0.75 caused false positives; 0.85 missed one cluster variant; 0.82 = 5/5 planted clusters, 0 false positives |
| Clustering algorithm | AgglomerativeClustering, average linkage | Average linkage avoids chaining (single) and is more lenient than complete; Ward requires Euclidean |
| Severity escalation | critical always; high + 3+ reports; any 5+ reports | Conservative — better to over-escalate to founders than miss a critical bug |
| Dedup "canonical" issue | Earliest `first_reported` | Preserves original reporter framing; most defensible tie-break |

---

## What I'd Do Differently at Scale

1. **Streaming ingestion**: Replace CSV batch with a Kafka topic or webhook endpoint so feedback is triaged in real-time, not nightly.

2. **Human-in-the-loop review queue**: Low-confidence classifications (conf < 0.7) should surface in a review UI (e.g., a Retool app) for a PM to confirm before entering the tracker.

3. **Local embedding model**: Replace the Gemini embedding API call with a local `all-MiniLM-L6-v2` (once torch is stable) for offline use, lower latency, and no per-call cost.

4. **Slack bot for real-time triage**: A Slack bot that listens to a `#feedback` channel and auto-threads triage results under each message, with 👍/👎 reactions to capture PM overrides as training signal.

5. **Active learning loop**: Use the `eval.py` hand-labels as a fine-tuning signal. After 200–300 labeled examples, distill a cheaper classification model that runs without LLM API calls.

6. **Structured DB migrations**: Replace the `schema.sql` init script with Alembic migrations so schema changes don't require a full DB rebuild.

7. **Multi-language support**: The current prompt is English-only. At scale, add language detection and route non-English feedback through a translation step before triage.

---

## Project Structure

```
├── generate_feedback.py      # Synthetic data generator
├── triage.py                 # LLM classification engine
├── dedup.py                  # Embedding-based deduplication
├── generate_bug_report.py    # Markdown bug report generator
├── weekly_summary.py         # Weekly digest generator
├── eval.py                   # Evaluation against hand labels
├── run_pipeline.py           # End-to-end orchestrator
├── schema.sql                # SQLite schema definition
├── tracker.db                # SQLite database (generated)
├── feedback_raw.csv          # Synthetic feedback (generated)
├── eval_sample.csv           # Hand-labeling sample (generated)
├── bug_reports/              # Bug .md files (generated)
│   └── bug_XXX_<slug>.md
├── weekly_summary_<date>.md  # Weekly digest (generated)
├── .env                      # API key (not committed)
└── .env.example              # Key template
```

---

*Built as a portfolio project demonstrating Product Ops & Analytics skills: LLM-based classification, embedding-based deduplication, structured data pipelines, and developer-facing documentation.*
