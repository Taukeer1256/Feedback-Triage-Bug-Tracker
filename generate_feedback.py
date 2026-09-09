"""
generate_feedback.py
====================
Generates 150-200 synthetic feedback items simulating a beta SaaS/consumer app
(a fictional project-management tool called "Flowboard").

Outputs: feedback_raw.csv

Design decisions / judgment calls flagged with ⚑:

⚑ CLUSTER SEEDING
  Five near-duplicate clusters are intentionally planted so the dedup step has
  real signal to detect. Each cluster shares a root issue but is rephrased,
  re-spelt, or comes from a different channel.  The cluster labels are stored in
  the CSV so eval.py can measure dedup accuracy separately from triage accuracy.

⚑ NOISE RATIO
  ~12% of items are pure noise (greetings, accidental sends, empty pings). This
  is on the low end of realistic; bump NOISE_FRACTION if you want a harder test.

⚑ TIMESTAMP DISTRIBUTION
  All items fall within the last 14 days so the weekly summary script has
  something to report on. Timestamps are skewed toward business hours (08:00-20:00)
  to simulate real usage patterns.

Usage:
    python generate_feedback.py              # saves feedback_raw.csv
    python generate_feedback.py --seed 99   # reproducible with different seed
    python generate_feedback.py --count 200 # override item count
"""

import argparse
import csv
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path


# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_FILE = Path("feedback_raw.csv")
APP_NAME = "Flowboard"
SOURCES = ["whatsapp", "email", "slack", "support_form"]
SOURCE_WEIGHTS = [0.25, 0.30, 0.25, 0.20]   # rough channel distribution

# Fraction of total items that are pure noise
NOISE_FRACTION = 0.12

# ── User pool ─────────────────────────────────────────────────────────────────
# 40 fictional users; some appear multiple times to simulate real usage
USER_IDS = [f"u{str(i).zfill(3)}" for i in range(1, 41)]


# ── Timestamp helper ──────────────────────────────────────────────────────────

def random_timestamp(days_back: int = 14) -> str:
    """Return a random ISO-8601 timestamp within the last `days_back` days,
    skewed toward business hours (08:00–20:00)."""
    base = datetime.now() - timedelta(days=random.uniform(0, days_back))
    hour = random.choices(
        range(24),
        weights=[1,1,1,1,1,1,1,1,4,5,5,5,4,4,5,5,5,4,3,3,2,2,1,1],
        k=1
    )[0]
    minute = random.randint(0, 59)
    return base.replace(hour=hour, minute=minute, second=random.randint(0, 59),
                        microsecond=0).isoformat()


# ── Noise items ───────────────────────────────────────────────────────────────

NOISE_TEXTS = [
    "hi",
    "Hello? Anyone there?",
    "test",
    "Is this the support channel?",
    "hey",
    "hello hello",
    "👋",
    "Is this thing on?",
    "Um hi, I think I sent this to the wrong place",
    "not sure if this is the right place lol",
    "ok thanks",
    "thanks!",
    "never mind figured it out",
    "disregard this",
    "............",
    "Just checking if notifications work",
    "testing 1 2 3",
    "Can someone call me instead?",
    "I'll send a proper email later",
    "My colleague told me to message here but idk what to say",
    "lgtm",
    "cool app",
    "👍",
    "Nice work team",
    "no issues so far!",
]


# ── Genuine bug reports (diverse, some with typos) ────────────────────────────

BUG_TEXTS = [
    # Login / auth bugs
    "The login page keeps spinning forever after I enter my password. Never actually logs me in.",
    "Cant log in at all. It just shows a white screen after clicking sign in",
    "2FA code says 'invalid' even when I enter it immediately. Had to disable 2FA to get in.",
    "When I click 'Forgot Password' I get a 404 error instead of the reset email.",
    "Session expires after like 5 minutes even though I'm actively using the app. Super annoying.",
    "Keep getting logged out randomly mid-session, lose all my unsaved work.",
    "The 'remember me' checkbox does nothing — still have to log in every single time.",

    # Data loss / sync bugs
    "I typed out a whole project description and it disappeared when I hit save. Lost everything.",
    "My tasks keep reverting to old states after I refresh. The updates aren't sticking.",
    "Comments I posted yesterday are gone today. Checked with my team and they can't see them either.",
    "Assigned a task to Sarah and the next day it showed as unassigned again.",
    "File attachment I uploaded showed a broken image — clicking it gives a 'file not found' error.",
    "Bulk-selected 20 tasks to mark complete, only the first one actually changed status.",

    # Notification bugs
    "Getting duplicate email notifications — same update, same task, three emails in a row.",
    "Push notifs aren't working on iOS at all since the last update.",
    "I disabled email notifications in settings but I'm still getting them.",
    "Late notification — got a 'task due' alert 2 days after the task was already due.",

    # Performance bugs
    "The dashboard takes forever to load. Like 30+ seconds. I've tried on different wifi.",
    "App completely crashes on my older Android phone (Samsung Galaxy S9) when I open any project.",
    "Exporting to CSV freezes the whole tab. Had to force-close the browser.",
    "The search function is incredibly slow. 10+ second delay before any results show.",

    # UI rendering bugs
    "Dark mode is broken — some text is white on white background, totally unreadable.",
    "The kanban board overlaps on mobile. Cards stack on top of each other.",
    "Dropdown menus don't close when I click outside them. Have to press Escape.",
    "The date picker shows the wrong month when I open it — always shows January for some reason.",
    "Filters panel disappears randomly and I have to reload the page to get it back.",

    # Integration bugs
    "Slack integration stopped posting updates to our channel — it was working last week.",
    "Google Calendar sync is off by one hour — all my tasks show up an hour late.",
    "The Zapier webhook isn't firing anymore. Tested it and no events are coming through.",

    # Miscellaneous bugs
    "Can't delete a project — the button appears greyed out even though I'm the owner.",
    "Clicking 'Duplicate task' creates a copy but the due date is always set to today, not copied.",
    "The timer feature on tasks adds time randomly in the background even when I'm not on the task.",
    "Keyboard shortcut 'Cmd+K' for quick search doesn't work on Mac.",
    "Profile picture upload fails silently — it looks like it uploaded but nothing changes.",
    "API rate limit errors appearing in the UI even on free tier (should only be paid users).",
]


# ── Feature requests ──────────────────────────────────────────────────────────

FEATURE_REQUEST_TEXTS = [
    "Would love a recurring task feature — right now I have to manually re-create monthly tasks.",
    "Can you add time tracking? I need to log hours per task for client billing.",
    "A Gantt chart view would be amazing for project timelines.",
    "Please add dark mode!! My eyes are dying on night shifts.",
    "Would be great to have a mobile app — the web app on phone is hard to use.",
    "Can we get sub-tasks? Need to break tasks into smaller steps.",
    "Export to PDF would be super useful for client reports.",
    "Integration with Notion would save me a ton of copy-paste work.",
    "A 'My Tasks' view that aggregates tasks across all my projects would be really helpful.",
    "Would love to be able to set custom fields on tasks — e.g. a 'client name' field.",
    "Bulk reassign tasks please! Reassigning one at a time is tedious with large projects.",
    "Would you consider adding a time zone setting per project? My team is distributed.",
    "An AI summary of project status at end of week would be cool.",
    "Can you add a template library for common project types?",
    "Please add read receipts for comments so I know if my teammate saw my note.",
    "Would love Markdown support in task descriptions.",
    "Can the search be global across all workspaces, not just current project?",
    "A burndown chart widget on the dashboard would help me track sprint velocity.",
    "Guest access / external collaborator role would be great for working with contractors.",
    "Offline mode — sometimes I'm on a train with no signal and I can't use the app at all.",
]


# ── UX confusion reports (sound like bugs but are actually design gaps) ────────

UX_CONFUSION_TEXTS = [
    "I can't figure out how to archive a project. The delete button just scares me, is there another option?",
    "Where do I find the activity log? I looked everywhere and couldn't find it.",
    "Thought the app was broken because nothing was loading — turned out I was in the wrong workspace.",
    "Why does 'Done' not move the task to the Completed column automatically? Confused.",
    "I set a due date but it never appeared on my calendar. Is that a feature or am I missing a step?",
    "Is there a way to sort tasks by priority? I found filters but no sort option.",
    "The difference between 'Close' and 'Archive' is really confusing. What does each one do exactly?",
    "I invited a team member but they said they never got the invite. Is there a pending invites page?",
    "Not sure if my changes saved or not — there's no confirmation message after saving.",
    "Took me 20 minutes to find where to change notification settings. It's buried.",
    "The permissions system is really confusing. What's the difference between Admin and Member?",
    "I keep accidentally creating duplicate projects because I can't tell when creation succeeded.",
    "Is there a way to see tasks assigned to multiple people? The filter only seems to do one user.",
    "I didn't realize comments were per-task until a teammate pointed it out. Thought they were global.",
    "Why can't I move tasks between projects? Is that not a feature?",
]


# ── Near-duplicate clusters (intentionally planted for dedup testing) ──────────
# Each sub-list is one cluster. cluster_id used in CSV for eval purposes.

DUPLICATE_CLUSTERS = {
    "cluster_A": {
        "root_issue": "Login spinner freezes indefinitely — user never gets authenticated",
        "variants": [
            # WhatsApp-style: casual, typos
            "the login is completely broken!! spiner just goes forever and never logs me in smh",
            # Email-style: formal
            "I'm experiencing an issue where the login screen displays a spinner indefinitely after I enter my credentials. The page never progresses to the dashboard.",
            # Slack-style: short
            "login broken for me too — just spins forever",
            # Support form: medium detail
            "Login doesn't work. I enter my email and password, click Sign In, and the loading spinner just keeps going. I've waited 5+ minutes. Nothing happens.",
            # Different angle — mentions clearing cache
            "Tried clearing cache but still can't log in. It just shows the spinning thing and hangs.",
            # Treats it as down
            "Is the app down? I can't get past the login screen, it's been stuck loading for an hour",
        ],
    },
    "cluster_B": {
        "root_issue": "Push notifications broken on iOS since last update",
        "variants": [
            "Push notifications have completely stopped working on my iPhone since yesterday's update.",
            "no notifs on iphone since update dropped ugh",
            "Hey I updated the app on iOS and now I'm getting zero push notifications. Anyone else?",
            "iOS push notifications are broken. Updated yesterday and nothing since.",
            "My iPhone stopped receiving any notifications from Flowboard after the latest version.",
        ],
    },
    "cluster_C": {
        "root_issue": "Task updates reverting to old state after page refresh",
        "variants": [
            "Every time I refresh the page, my task updates disappear and go back to what they were before.",
            "Changes don't save!! I mark something done, refresh, and it's back to incomplete.",
            "task status keeps reverting. is there an autosave bug?",
            "I updated a task's status to 'In Progress' three times now and it keeps going back to 'To Do' after I reload.",
            "noticed that whenever I close and reopen the app my edits to tasks are lost - the old data comes back",
        ],
    },
    "cluster_D": {
        "root_issue": "Duplicate email notifications being sent for single events",
        "variants": [
            "I keep getting the same email notification 3 times for every single task update. Please fix!",
            "Getting spammed by email — every comment on a task sends me like 4 identical emails.",
            "duplicate email notifs are really annoying. same message 2-3x every time",
            "The email notifications are duplicated. I receive 2-3 copies of the same notification for one event.",
            "Can someone look at the email notification system? Getting tripicate [sic] emails for every change.",
        ],
    },
    "cluster_E": {
        "root_issue": "CSV export freezes the browser tab",
        "variants": [
            "exporting to CSV completely freezes my browser tab. have to force quit chrome every time",
            "The CSV export feature crashes my browser. Tab becomes unresponsive.",
            "Tried to export my project to CSV and the browser just froze. Had to kill the tab.",
            "CSV export = instant browser freeze. Happens 100% of the time on Chrome 125.",
            "Export button is broken — when I click 'Export to CSV' the whole page hangs and I have to reload.",
        ],
    },
}


# ── Generator ─────────────────────────────────────────────────────────────────

def build_item(
    raw_text: str,
    source: str | None = None,
    user_id: str | None = None,
    cluster_id: str | None = None,
    category_hint: str | None = None,
) -> dict:
    """Build a single feedback row dict."""
    return {
        "id": str(uuid.uuid4()),
        "source": source or random.choices(SOURCES, SOURCE_WEIGHTS)[0],
        "timestamp": random_timestamp(),
        "raw_text": raw_text,
        "user_id": user_id or random.choice(USER_IDS),
        # cluster_id is set for planted duplicates; NULL/"" for everything else.
        # The triage and dedup scripts DO NOT read this column — it exists solely
        # for eval.py to measure dedup accuracy.
        "cluster_id": cluster_id or "",
        # category_hint is informational for labeling; the triage engine ignores it.
        "category_hint": category_hint or "",
    }


def generate_items(target_count: int) -> list[dict]:
    items: list[dict] = []

    # 1. Plant all duplicate cluster variants first
    for cid, cluster in DUPLICATE_CLUSTERS.items():
        for i, text in enumerate(cluster["variants"]):
            source = random.choices(SOURCES, SOURCE_WEIGHTS)[0]
            items.append(build_item(
                raw_text=text,
                source=source,
                cluster_id=cid,
                category_hint="bug",
            ))

    planted_count = len(items)  # should be 26 variants across 5 clusters

    # Remaining budget split by category
    remaining = target_count - planted_count
    n_noise = int(remaining * NOISE_FRACTION)
    n_bugs = int(remaining * 0.30)
    n_features = int(remaining * 0.28)
    n_ux = int(remaining * 0.20)
    # Remainder goes to noise to hit target exactly
    n_noise += remaining - n_noise - n_bugs - n_features - n_ux

    # 2. Bugs
    for _ in range(n_bugs):
        items.append(build_item(
            raw_text=random.choice(BUG_TEXTS),
            category_hint="bug",
        ))

    # 3. Feature requests
    for _ in range(n_features):
        items.append(build_item(
            raw_text=random.choice(FEATURE_REQUEST_TEXTS),
            category_hint="feature_request",
        ))

    # 4. UX confusion
    for _ in range(n_ux):
        items.append(build_item(
            raw_text=random.choice(UX_CONFUSION_TEXTS),
            category_hint="ux_confusion",
        ))

    # 5. Noise
    for _ in range(n_noise):
        items.append(build_item(
            raw_text=random.choice(NOISE_TEXTS),
            category_hint="noise",
        ))

    # Shuffle so duplicates aren't all at the top
    random.shuffle(items)
    return items


def save_csv(items: list[dict], path: Path) -> None:
    fieldnames = ["id", "source", "timestamp", "raw_text", "user_id", "cluster_id", "category_hint"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Generate synthetic feedback data for the {APP_NAME} bug tracker."
    )
    parser.add_argument(
        "--count", type=int, default=175,
        help="Approximate number of feedback items to generate (default: 175)."
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)."
    )
    parser.add_argument(
        "--output", type=str, default=str(OUTPUT_FILE),
        help=f"Output CSV path (default: {OUTPUT_FILE})."
    )
    args = parser.parse_args()

    random.seed(args.seed)
    output_path = Path(args.output)

    print(f"Generating ~{args.count} feedback items (seed={args.seed})...")
    items = generate_items(args.count)
    save_csv(items, output_path)

    # ── Summary stats ──
    from collections import Counter
    cats = Counter(i["category_hint"] for i in items)
    sources = Counter(i["source"] for i in items)
    clusters = Counter(i["cluster_id"] for i in items if i["cluster_id"])

    print(f"\n[OK] Saved {len(items)} items to {output_path}")
    print("\nCategory breakdown (hint — not the LLM label):")
    for cat, count in sorted(cats.items()):
        bar = "|" * (count // 2)
        print(f"  {cat:<20} {count:>3}  {bar}")
    print("\nSource breakdown:")
    for src, count in sorted(sources.items()):
        bar = "|" * (count // 2)
        print(f"  {src:<20} {count:>3}  {bar}")
    print("\nPlanted duplicate clusters:")
    for cid, count in sorted(clusters.items()):
        root = DUPLICATE_CLUSTERS[cid]["root_issue"]
        print(f"  {cid}: {count} variants  -> \"{root[:60]}...\"")
    print(f"\nTotal planted near-duplicate variants: {sum(clusters.values())} across {len(clusters)} clusters")
    print("\nNext step: run  python triage.py  to classify these items.")


if __name__ == "__main__":
    main()
