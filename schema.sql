-- =============================================================================
-- Feedback Triage & Bug Tracker — SQLite Schema
-- =============================================================================
-- Run this via: sqlite3 tracker.db < schema.sql
-- Or use the Python init_db() helper in db.py which calls this automatically.
--
-- JUDGMENT CALL: We store "canonical_summary" on the issues table (not raw_reports)
-- because the goal is a single actionable description per issue that devs see first.
-- The raw text is always recoverable from raw_reports for full context.
-- =============================================================================

PRAGMA foreign_keys = ON;   -- enforce FK constraints every time the DB is opened

-- ── ISSUES ───────────────────────────────────────────────────────────────────
-- One row per unique tracked issue (after deduplication).
-- "report_count" is a denormalised count for fast ranking; kept in sync by
-- the dedup step rather than computed at query time.
CREATE TABLE IF NOT EXISTS issues (
    id                INTEGER  PRIMARY KEY AUTOINCREMENT,
    category          TEXT     NOT NULL CHECK(category IN (
                          'bug', 'feature_request', 'ux_confusion', 'duplicate', 'noise'
                      )),
    severity          TEXT     CHECK(severity IN ('low', 'medium', 'high', 'critical')),
    -- NULL is valid for non-bug categories
    frequency         TEXT     CHECK(frequency IN ('isolated', 'recurring')),
    -- NULL is valid for non-bug categories
    status            TEXT     NOT NULL DEFAULT 'open'
                               CHECK(status IN ('open', 'escalated', 'resolved', 'wontfix')),
    first_reported    TEXT     NOT NULL,   -- ISO-8601 timestamp (stored as TEXT per SQLite convention)
    last_reported     TEXT     NOT NULL,   -- updated each time a duplicate is merged in
    report_count      INTEGER  NOT NULL DEFAULT 1,
    canonical_summary TEXT     NOT NULL,  -- LLM-generated one-liner used in reports & weekly digest
    cluster_id        INTEGER,             -- which dedup cluster this issue belongs to (NULL = singleton)
    created_at        TEXT     NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT     NOT NULL DEFAULT (datetime('now'))
);

-- ── RAW REPORTS ──────────────────────────────────────────────────────────────
-- One row per original feedback item, always preserved verbatim.
-- issue_id is set after triage/dedup; NULL means "not yet triaged".
CREATE TABLE IF NOT EXISTS raw_reports (
    id                INTEGER  PRIMARY KEY AUTOINCREMENT,
    issue_id          INTEGER  REFERENCES issues(id) ON DELETE SET NULL,
    source            TEXT     NOT NULL CHECK(source IN ('whatsapp', 'email', 'slack', 'support_form')),
    raw_text          TEXT     NOT NULL,
    user_id           TEXT     NOT NULL,
    timestamp         TEXT     NOT NULL,   -- ISO-8601
    triage_category   TEXT,                -- category assigned during triage (before dedup merging)
    triage_confidence REAL,                -- 0.0-1.0 from LLM
    triage_rationale  TEXT,                -- LLM one-line rationale
    ingested_at       TEXT     NOT NULL DEFAULT (datetime('now'))
);

-- ── INDEXES ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_raw_reports_issue_id  ON raw_reports(issue_id);
CREATE INDEX IF NOT EXISTS idx_raw_reports_timestamp ON raw_reports(timestamp);
CREATE INDEX IF NOT EXISTS idx_issues_category       ON issues(category);
CREATE INDEX IF NOT EXISTS idx_issues_status         ON issues(status);
CREATE INDEX IF NOT EXISTS idx_issues_severity       ON issues(severity);
CREATE INDEX IF NOT EXISTS idx_issues_report_count   ON issues(report_count DESC);
