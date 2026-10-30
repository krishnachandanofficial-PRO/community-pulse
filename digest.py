"""
digest.py — owned by Krishna

Reads cache.json + health score and sends a weekly Discord digest.

What this file does, in plain English (be ready to explain this line-by-line):
  1. Load the cached GitHub data from cache.json.
  2. Score every open PR / issue using a four-factor priority formula.
  3. Pick the top items for each of three queues:
       • Ready for Review    – PRs with no review yet, longest waiting
       • Newcomer Support    – first-timers waiting for a meaningful reply
       • Needs Attention     – items with failed checks / missing info / duplicates
  4. Format a Discord message (Discord Embeds via webhook JSON).
  5. POST it to the Discord webhook URL from .env.
  6. Print the same summary to the terminal as well.

Run in test mode (prints only, no POST):
    python digest.py --test

Run for real:
    python digest.py

Run for a different repo (must already be cached):
    python digest.py --repo fastapi/fastapi
"""

import argparse
import json
import os
import statistics
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
CACHE_FILE          = "cache.json"

# ─────────────────────────────────────────────────────────────────
# Priority weights (section 1 of the implementation spec)
# Maintainers can adjust these.
# ─────────────────────────────────────────────────────────────────
WEIGHTS = {
    "wait_time":   0.50,   # how long it has been waiting
    "repo_prio":   0.25,   # label-based repository priority
    "newcomer":    0.15,   # whether the author is a first-time contributor
    "readiness":   0.10,   # whether the PR/issue has everything needed
}

BOT_SUFFIXES = ("[bot]", "-bot", "bot")

# Labels that signal high repository priority
HIGH_PRIO_LABELS = {"critical", "priority: high", "priority:high",
                    "urgent", "important", "security", "bug",
                    "good first issue", "help wanted"}


# ─────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────

def _load_cache(path: str = CACHE_FILE) -> dict:
    with open(path) as f:
        return json.load(f)


def _parse(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def _is_bot(login: str) -> bool:
    login = login.lower()
    return any(login.endswith(s) for s in BOT_SUFFIXES)


def _age_minutes(item: dict) -> float:
    created = _parse(item.get("created_at"))
    if not created:
        return 0.0
    now = datetime.now(timezone.utc)
    return (now - created).total_seconds() / 60


def _has_real_reply(item: dict) -> bool:
    """True if at least one non-author, non-bot comment exists."""
    author = item.get("user", {}).get("login", "")
    for c in item.get("_comments", []):
        commenter = c.get("user", {}).get("login", "")
        if commenter != author and not _is_bot(commenter):
            return True
    return False


def _has_review(item: dict) -> bool:
    return bool(item.get("_reviews"))


def _is_pr(item: dict) -> bool:
    return "pull_request" in item


def _is_open(item: dict) -> bool:
    return item.get("state", "open") == "open"


def _labels(item: dict) -> set[str]:
    return {lbl["name"].lower() for lbl in item.get("labels", [])}


# ─────────────────────────────────────────────────────────────────
# Identify newcomers
# A newcomer = author who appears only once or twice in the whole snapshot.
# ─────────────────────────────────────────────────────────────────

def _build_author_count(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        login = item.get("user", {}).get("login", "")
        if login and not _is_bot(login):
            counts[login] = counts.get(login, 0) + 1
    return counts


# ─────────────────────────────────────────────────────────────────
# Priority scoring (section 1 of spec)
# ─────────────────────────────────────────────────────────────────

def _priority_score(item: dict, author_counts: dict[str, int],
                    max_age_min: float) -> tuple[float, dict]:
    """
    Returns (composite_score 0–100, reason_dict).

    Factors:
      wait_time  – normalised age (0–100)
      repo_prio  – label match (0 or 100)
      newcomer   – author count == 1 → 100, else 0
      readiness  – open + no blocking label → 100, else 50
    """
    age   = _age_minutes(item)
    login = item.get("user", {}).get("login", "")
    lbls  = _labels(item)

    # 1. Wait time: normalise against the oldest item in this run
    wait_score = min(100.0, age / max(max_age_min, 1) * 100)

    # 2. Repo priority: any matching label?
    repo_score = 100.0 if lbls & HIGH_PRIO_LABELS else 40.0

    # 3. Newcomer support: first-timer?
    newcomer_score = 100.0 if author_counts.get(login, 0) == 1 else 0.0

    # 4. Readiness: is the item actually ready to act on?
    blocking = {"wip", "work in progress", "draft", "do not merge", "hold"}
    readiness_score = 30.0 if lbls & blocking else 100.0

    composite = (
        WEIGHTS["wait_time"] * wait_score
        + WEIGHTS["repo_prio"] * repo_score
        + WEIGHTS["newcomer"] * newcomer_score
        + WEIGHTS["readiness"] * readiness_score
    )

    reasons = []
    if wait_score >= 80:
        reasons.append(f"waiting {round(age/60/24, 1)} days")
    if repo_score == 100:
        matched = lbls & HIGH_PRIO_LABELS
        reasons.append(f"label: {next(iter(matched))}")
    if newcomer_score == 100:
        reasons.append("first-time contributor")
    if readiness_score == 30:
        reasons.append("blocked / draft")

    return round(composite, 1), {
        "wait": round(wait_score, 1),
        "repo": repo_score,
        "newcomer": newcomer_score,
        "readiness": readiness_score,
        "composite": round(composite, 1),
        "reason_text": "; ".join(reasons) if reasons else "moderate priority",
    }


# ─────────────────────────────────────────────────────────────────
# Three queues (section 3 of spec)
# ─────────────────────────────────────────────────────────────────

def build_queues(items: list[dict]) -> dict:
    """
    Returns three prioritised queues:
      ready_for_review  – open PRs with NO review yet
      newcomer_support  – open items by first-timers with no real reply
      needs_attention   – open items with issues (missing info, etc.)

    Each entry: {item, score, reasons}
    """
    open_items    = [it for it in items if _is_open(it)]
    author_counts = _build_author_count(items)
    ages          = [_age_minutes(it) for it in open_items]
    max_age       = max(ages) if ages else 1.0

    ready_for_review = []
    newcomer_support = []
    needs_attention  = []

    for item in open_items:
        score, reasons = _priority_score(item, author_counts, max_age)
        entry = {
            "number":  item["number"],
            "title":   item.get("title", ""),
            "login":   item.get("user", {}).get("login", ""),
            "html_url": item.get("html_url", ""),
            "is_pr":   _is_pr(item),
            "age_hrs": round(_age_minutes(item) / 60, 1),
            "score":   score,
            "reasons": reasons,
        }

        if _is_pr(item) and not _has_review(item):
            ready_for_review.append(entry)

        login = item.get("user", {}).get("login", "")
        if author_counts.get(login, 0) == 1 and not _has_real_reply(item):
            newcomer_support.append(entry)

        lbls = _labels(item)
        blocking_labels = {"invalid", "needs more info", "waiting for author",
                           "needs-info", "triage"}
        if lbls & blocking_labels:
            needs_attention.append(entry)

    # Sort each queue by priority score descending
    key = lambda e: e["score"]
    ready_for_review.sort(key=key, reverse=True)
    newcomer_support.sort(key=key, reverse=True)
    needs_attention.sort(key=key, reverse=True)

    return {
        "ready_for_review": ready_for_review[:5],
        "newcomer_support": newcomer_support[:5],
        "needs_attention":  needs_attention[:5],
    }


# ─────────────────────────────────────────────────────────────────
# Next Best Action (section 10 of spec)
# ─────────────────────────────────────────────────────────────────

def next_best_action(entry: dict) -> str:
    """Return a one-line recommended action for a queued item."""
    reasons = entry.get("reasons", {})
    if entry["is_pr"] and not entry.get("reviewed", True):
        return "👀 Review this PR"
    if reasons.get("newcomer") == 100.0:
        return "🤝 Welcome & guide this newcomer"
    if "blocked / draft" in reasons.get("reason_text", ""):
        return "⏸ Wait — item is blocked/draft"
    if entry["age_hrs"] > 72:
        return "⚡ Assign a reviewer or respond now"
    return "📋 Review and triage"


# ─────────────────────────────────────────────────────────────────
# Format Discord message
# ─────────────────────────────────────────────────────────────────

def _fmt_item(entry: dict, idx: int) -> str:
    kind   = "PR" if entry["is_pr"] else "Issue"
    nba    = next_best_action(entry)
    reason = entry["reasons"].get("reason_text", "")
    return (
        f"**{idx}. [{kind} #{entry['number']}]({entry['html_url']})** — "
        f"{entry['title'][:70]}{'…' if len(entry['title']) > 70 else ''}\n"
        f"   👤 `{entry['login']}`  ⏱ {entry['age_hrs']}h  🎯 Score: {entry['score']}\n"
        f"   💡 {reason}\n"
        f"   ➡ **{nba}**"
    )


def build_discord_payload(repo: str, queues: dict, health: dict,
                          metrics: dict) -> dict:
    """
    Build the Discord webhook JSON payload (Embeds format).
    Discord embed colour:
      green  (0x2ecc71) → health A/B
      yellow (0xf39c12) → C
      red    (0xe74c3c) → D/F
    """
    grade  = health.get("grade", "?")
    score  = health.get("score", 0)
    colour = (0x2ecc71 if grade in ("A", "B")
              else 0xf39c12 if grade == "C"
              else 0xe74c3c)

    # Build fields for each queue
    def queue_field(name: str, emoji: str, entries: list[dict]) -> dict:
        if not entries:
            return {"name": f"{emoji} {name}", "value": "_Nothing here — great!_", "inline": False}
        lines = [_fmt_item(e, i + 1) for i, e in enumerate(entries[:3])]
        return {"name": f"{emoji} {name}", "value": "\n\n".join(lines), "inline": False}

    # Metric summary line
    frt  = metrics.get("median_first_response_min")
    prw  = metrics.get("median_pr_review_wait_min")
    ret  = (metrics.get("newcomer_retention") or {}).get("retention_pct")
    fn   = metrics.get("contributor_funnel", {})
    frt_txt = f"{round(frt/60,1)}h" if frt else "n/a"
    prw_txt = f"{round(prw/60,1)}h" if prw else "n/a"
    ret_txt = f"{ret}%" if ret is not None else "n/a"

    item_count = metrics.get("item_count", "?")
    fetched    = metrics.get("fetched_at", "")[:10]

    description = (
        f"**Community Health Score: {score}/100 — Grade {grade}**\n\n"
        f"📊 `{item_count}` items analysed (snapshot: {fetched})\n"
        f"⏱ Median first response: **{frt_txt}** · "
        f"PR review wait: **{prw_txt}**\n"
        f"🔁 Newcomer retention: **{ret_txt}** · "
        f"Repeat contributors: **{fn.get('stage3_repeat', 'n/a')}**"
    )

    embeds = [
        {
            "title": f"📡 Community Pulse — {repo}",
            "description": description,
            "color": colour,
            "fields": [
                queue_field("Ready for Review",   "✅", queues["ready_for_review"]),
                queue_field("Newcomer Support",    "🌱", queues["newcomer_support"]),
                queue_field("Needs Attention",     "⚠️",  queues["needs_attention"]),
            ],
            "footer": {
                "text": "Community Pulse · Team Git Guardians · Devf8rge PS-02 Track 1"
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ]
    return {"embeds": embeds}


# ─────────────────────────────────────────────────────────────────
# Terminal summary (mirrors what Discord shows)
# ─────────────────────────────────────────────────────────────────

def print_summary(repo: str, queues: dict, health: dict, metrics: dict):
    grade  = health.get("grade", "?")
    score  = health.get("score", 0)
    frt    = metrics.get("median_first_response_min")
    prw    = metrics.get("median_pr_review_wait_min")
    ret    = (metrics.get("newcomer_retention") or {}).get("retention_pct")
    fn     = metrics.get("contributor_funnel", {})

    print()
    print("=" * 60)
    print(f"  COMMUNITY PULSE — {repo}")
    print("=" * 60)
    print(f"  Health Score : {score}/100  Grade {grade}")
    print(f"  First Response (median) : {round(frt/60,1)}h" if frt else "  First Response : n/a")
    print(f"  PR Review Wait (median) : {round(prw/60,1)}h" if prw else "  PR Review Wait : n/a")
    print(f"  Newcomer Retention      : {ret}%" if ret is not None else "  Newcomer Retention : n/a")
    print(f"  Repeat contributors     : {fn.get('stage3_repeat', 'n/a')}")
    print()

    for queue_name, emoji in [
        ("ready_for_review", "✅ Ready for Review"),
        ("newcomer_support", "🌱 Newcomer Support"),
        ("needs_attention",  "⚠  Needs Attention"),
    ]:
        entries = queues[queue_name]
        print(f"  {emoji}")
        if not entries:
            print("    (none)")
        for e in entries:
            kind = "PR" if e["is_pr"] else "Issue"
            nba  = next_best_action(e)
            print(f"    [{kind} #{e['number']}] {e['title'][:55]}…")
            print(f"      Score {e['score']} | {e['age_hrs']}h old | {nba}")
        print()
    print("=" * 60)
    print()


# ─────────────────────────────────────────────────────────────────
# Send to Discord
# ─────────────────────────────────────────────────────────────────

def send_discord(payload: dict, webhook_url: str) -> bool:
    """POST the embed payload to Discord. Returns True on success."""
    resp = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    if resp.status_code in (200, 204):
        print("[digest] ✅ Discord message sent successfully.")
        return True
    else:
        print(f"[digest] ❌ Discord returned {resp.status_code}: {resp.text[:200]}")
        return False


# ─────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────

def run(test_mode: bool = False, cache_path: str = CACHE_FILE):
    # 1. Load cache
    try:
        data = _load_cache(cache_path)
    except FileNotFoundError:
        print(f"[digest] ❌ {cache_path} not found. Run fetch.py first.")
        return

    items = data["items"]
    repo  = data.get("repo", "unknown/repo")

    # 2. Build queues
    queues = build_queues(items)

    # 3. Calculate health (import lazily to avoid circular issues)
    from metrics import all_metrics
    from health  import health_score
    metrics = all_metrics(cache_path)
    health  = health_score(metrics)

    # 4. Print terminal summary
    print_summary(repo, queues, health, metrics)

    if test_mode:
        print("[digest] 🧪 Test mode — Discord NOT called.")
        payload = build_discord_payload(repo, queues, health, metrics)
        print("[digest] Payload preview (first 800 chars):")
        print(json.dumps(payload, indent=2)[:800], "…")
        return

    # 5. Send to Discord
    if not DISCORD_WEBHOOK_URL:
        print("[digest] ❌ DISCORD_WEBHOOK_URL not set in .env. Skipping send.")
        return

    payload = build_discord_payload(repo, queues, health, metrics)
    send_discord(payload, DISCORD_WEBHOOK_URL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Community Pulse — Discord digest")
    parser.add_argument("--test", action="store_true",
                        help="Print summary and payload but do NOT send to Discord")
    parser.add_argument("--repo", default=None,
                        help="Override GITHUB_REPO from .env")
    args = parser.parse_args()

    run(test_mode=args.test)
