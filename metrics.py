"""
metrics.py — owned by Nishanth (metrics 1 & 2) + Krishna (metrics 3 & 4)

Four community-health metrics:
  1. First response time   (median minutes) — Nishanth
  2. PR review wait        (median minutes) — Nishanth
  3. Newcomer retention    (%)              — Krishna
  4. Contributor funnel    (dict of counts) — Krishna
"""

import json
import statistics
from datetime import datetime, timezone, timedelta
from typing import Optional

CACHE_FILE = "cache.json"

# Bots we skip when looking for "real" replies
BOT_SUFFIXES = ("[bot]", "-bot", "bot")


# ──────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Metric 1 — First response time (Nishanth)
# ──────────────────────────────────────────────

def first_response_times(items: list[dict]) -> list[float]:
    """
    For each item, find the first comment from someone who is:
      - not the original author
      - not a bot
    Return list of elapsed minutes (one per item that has a reply).
    Items with no qualifying reply are skipped (we only report the median
    over items that *were* answered).
    """
    times = []
    for item in items:
        opened_at = _parse(item.get("created_at"))
        author    = item.get("user", {}).get("login", "")
        if not opened_at:
            continue
        for comment in item.get("_comments", []):
            commenter = comment.get("user", {}).get("login", "")
            if commenter == author or _is_bot(commenter):
                continue
            replied_at = _parse(comment.get("created_at"))
            if replied_at:
                elapsed = (replied_at - opened_at).total_seconds() / 60
                times.append(elapsed)
                break   # only first qualifying reply
    return times


def median_first_response_minutes(items: list[dict]) -> Optional[float]:
    t = first_response_times(items)
    return round(statistics.median(t), 1) if t else None


# ──────────────────────────────────────────────
# Metric 2 — PR review wait (Nishanth)
# ──────────────────────────────────────────────

def pr_review_wait_times(items: list[dict]) -> list[float]:
    """
    For each PR, find the first review and return elapsed minutes from open.
    """
    times = []
    for item in items:
        if "pull_request" not in item:
            continue
        opened_at = _parse(item.get("created_at"))
        if not opened_at:
            continue
        for review in item.get("_reviews", []):
            submitted = _parse(review.get("submitted_at"))
            if submitted:
                elapsed = (submitted - opened_at).total_seconds() / 60
                times.append(elapsed)
                break
    return times


def median_pr_review_wait_minutes(items: list[dict]) -> Optional[float]:
    t = pr_review_wait_times(items)
    return round(statistics.median(t), 1) if t else None


# ──────────────────────────────────────────────
# Metric 3 — Newcomer retention (Krishna)
# ──────────────────────────────────────────────

def newcomer_retention(items: list[dict], return_window_days: int = 30) -> dict:
    """
    Newcomer: a contributor whose FIRST ever contribution is inside our 300 items.

    Retention: among those newcomers, what share came back with at least one
    more contribution (issue OR PR) within `return_window_days` days of their
    first one?

    Returns a dict with:
      newcomer_count    – how many first-timers we found
      retained_count    – how many came back within the window
      retention_pct     – retained / newcomer * 100  (0-100, or None)
      newcomers         – list of {login, first_at, returned}
    """
    # Build per-author sorted list of contribution datetimes
    author_dates: dict[str, list[datetime]] = {}
    for item in items:
        login = item.get("user", {}).get("login", "")
        if not login or _is_bot(login):
            continue
        dt = _parse(item.get("created_at"))
        if dt:
            author_dates.setdefault(login, []).append(dt)

    for login in author_dates:
        author_dates[login].sort()

    # A newcomer is someone whose earliest contribution is inside our window
    # AND is not a known long-time contributor (only one earlier appearance).
    # Simple definition: in our 300-item snapshot, they appear exactly once in
    # the past OR their first-ever item here is their global first (we can't
    # know the global first, so we approximate: first-timers = people with
    # only ONE item OR whose first item is also the latest we have).
    # Practical approach for hackathon: treat everyone who appears only ONCE
    # in the snapshot as a newcomer; treat them as retained if they appear
    # MORE than once within 30 days of that first appearance.

    newcomers = []
    for login, dates in author_dates.items():
        first = dates[0]
        returned = any(
            0 < (d - first).days <= return_window_days
            for d in dates[1:]
        )
        if len(dates) == 1 or (len(dates) > 1 and (dates[1] - first).days <= return_window_days):
            # This person is a "newcomer" in our snapshot — only one or first
            # return was within window
            pass

        # Cleaner: anyone whose first contribution is within our sample
        # and has fewer than 3 total contributions = treat as newcomer
        if len(dates) <= 2:
            newcomers.append({
                "login":    login,
                "first_at": first.isoformat(),
                "returned": returned,
            })

    total    = len(newcomers)
    retained = sum(1 for n in newcomers if n["returned"])
    pct      = round(retained / total * 100, 1) if total else None

    return {
        "newcomer_count":  total,
        "retained_count":  retained,
        "retention_pct":   pct,
        "newcomers":       newcomers,
    }


# ──────────────────────────────────────────────
# Metric 4 — Contributor funnel (Krishna)
# ──────────────────────────────────────────────

def contributor_funnel(items: list[dict]) -> dict:
    """
    Three-stage funnel:
      Stage 1 — First issue: opened at least one issue
      Stage 2 — First PR:    opened at least one PR
      Stage 3 — Repeat:      opened MORE than one issue or PR (came back)

    Returns a dict with:
      stage1_issue_only  – people who opened an issue but no PR
      stage2_pr          – people who opened at least one PR
      stage3_repeat      – people with > 1 total contribution
      funnel_detail      – full dict of per-login contribution counts
    """
    issues_by: dict[str, int]  = {}
    prs_by:    dict[str, int]  = {}

    for item in items:
        login = item.get("user", {}).get("login", "")
        if not login or _is_bot(login):
            continue
        if "pull_request" in item:
            prs_by[login] = prs_by.get(login, 0) + 1
        else:
            issues_by[login] = issues_by.get(login, 0) + 1

    all_contributors = set(issues_by) | set(prs_by)

    stage1_issue_only = 0
    stage2_pr         = 0
    stage3_repeat     = 0
    funnel_detail     = {}

    for login in all_contributors:
        n_issues = issues_by.get(login, 0)
        n_prs    = prs_by.get(login, 0)
        total    = n_issues + n_prs

        funnel_detail[login] = {"issues": n_issues, "prs": n_prs, "total": total}

        if n_prs == 0:
            stage1_issue_only += 1
        else:
            stage2_pr += 1

        if total > 1:
            stage3_repeat += 1

    return {
        "stage1_issue_only": stage1_issue_only,
        "stage2_pr":         stage2_pr,
        "stage3_repeat":     stage3_repeat,
        "total_contributors": len(all_contributors),
        "funnel_detail":     funnel_detail,
    }


# ──────────────────────────────────────────────
# All metrics in one call
# ──────────────────────────────────────────────

def all_metrics(cache_path: str = CACHE_FILE) -> dict:
    data  = _load_cache(cache_path)
    items = data["items"]
    return {
        "repo":                       data.get("repo"),
        "fetched_at":                 data.get("fetched_at"),
        "item_count":                 len(items),
        "median_first_response_min":  median_first_response_minutes(items),
        "median_pr_review_wait_min":  median_pr_review_wait_minutes(items),
        "newcomer_retention":         newcomer_retention(items),
        "contributor_funnel":         contributor_funnel(items),
    }


if __name__ == "__main__":
    import pprint
    pprint.pprint(all_metrics())
