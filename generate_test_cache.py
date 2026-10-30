#!/usr/bin/env python3
"""
generate_test_cache.py
Creates a realistic cache.json for offline testing / demo purposes.
Run once: python generate_test_cache.py
"""
import json
from datetime import datetime, timezone, timedelta

NOW = datetime.now(timezone.utc)

def dt(days_ago: float, hours: float = 0) -> str:
    return (NOW - timedelta(days=days_ago, hours=hours)).isoformat()

items = [
    # ── PRs ──────────────────────────────────────────────────────────────
    {
        "number": 101, "title": "Fix: null pointer in auth middleware",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/pull/101",
        "created_at": dt(5), "user": {"login": "alice"},
        "labels": [{"name": "bug"}, {"name": "priority: high"}],
        "pull_request": {}, "_reviews": [], "_comments": []
    },
    {
        "number": 102, "title": "Docs: add example for dependency injection",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/pull/102",
        "created_at": dt(2), "user": {"login": "new_contributor_1"},
        "labels": [{"name": "documentation"}],
        "pull_request": {}, "_reviews": [], "_comments": []
    },
    {
        "number": 103, "title": "Feat: add rate limiting middleware",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/pull/103",
        "created_at": dt(8), "user": {"login": "bob"},
        "labels": [{"name": "feature"}],
        "pull_request": {},
        "_reviews": [{"submitted_at": dt(7), "state": "COMMENTED",
                      "user": {"login": "maintainer1"}}],
        "_comments": [{"created_at": dt(7, 2), "user": {"login": "maintainer1"},
                       "body": "Looks good, needs tests."}]
    },
    {
        "number": 104, "title": "WIP: refactor router (not ready)",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/pull/104",
        "created_at": dt(1), "user": {"login": "new_contributor_2"},
        "labels": [{"name": "wip"}],
        "pull_request": {}, "_reviews": [], "_comments": []
    },
    {
        "number": 105, "title": "Fix: response model validation edge case",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/pull/105",
        "created_at": dt(12), "user": {"login": "carol"},
        "labels": [{"name": "bug"}],
        "pull_request": {},
        "_reviews": [],
        "_comments": [{"created_at": dt(11), "user": {"login": "maintainer2"},
                       "body": "Can you add a test case?"}]
    },
    # ── Issues ────────────────────────────────────────────────────────────
    {
        "number": 201, "title": "Question: how to set custom response headers?",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/issues/201",
        "created_at": dt(3), "user": {"login": "new_contributor_3"},
        "labels": [{"name": "question"}],
        "_reviews": [],
        "_comments": []   # newcomer with NO reply — should appear in newcomer queue
    },
    {
        "number": 202, "title": "Bug: 422 error when body is None",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/issues/202",
        "created_at": dt(6), "user": {"login": "dave"},
        "labels": [{"name": "bug"}, {"name": "needs-info"}],
        "_reviews": [],
        "_comments": [{"created_at": dt(5), "user": {"login": "maintainer1"},
                       "body": "Please share a minimal reproducible example."}]
    },
    {
        "number": 203, "title": "Improve error messages for validation",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/issues/203",
        "created_at": dt(15), "user": {"login": "alice"},  # alice repeats
        "labels": [{"name": "enhancement"}],
        "_reviews": [],
        "_comments": [{"created_at": dt(14), "user": {"login": "maintainer2"},
                       "body": "Good idea, accepting PR."}]
    },
    {
        "number": 204, "title": "Security: path traversal in static files",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/issues/204",
        "created_at": dt(1, 3), "user": {"login": "security_researcher"},
        "labels": [{"name": "security"}, {"name": "critical"}],
        "_reviews": [],
        "_comments": []
    },
    {
        "number": 205, "title": "First contribution: small typo in README",
        "state": "open", "html_url": "https://github.com/fastapi/fastapi/issues/205",
        "created_at": dt(0, 6), "user": {"login": "new_contributor_4"},
        "labels": [{"name": "good first issue"}],
        "_reviews": [],
        "_comments": []
    },
    # Closed items (for metrics calculations)
    {
        "number": 301, "title": "Add Python 3.12 support",
        "state": "closed", "html_url": "https://github.com/fastapi/fastapi/pull/301",
        "created_at": dt(20), "user": {"login": "carol"},
        "labels": [],
        "pull_request": {},
        "_reviews": [{"submitted_at": dt(18), "state": "APPROVED",
                      "user": {"login": "maintainer1"}}],
        "_comments": [{"created_at": dt(19), "user": {"login": "maintainer1"},
                       "body": "Merging this."}]
    },
    {
        "number": 302, "title": "Fix: headers not forwarded in TestClient",
        "state": "closed", "html_url": "https://github.com/fastapi/fastapi/issues/302",
        "created_at": dt(25), "user": {"login": "bob"},  # bob repeats
        "labels": [{"name": "bug"}],
        "_reviews": [],
        "_comments": [{"created_at": dt(24, 4), "user": {"login": "maintainer2"},
                       "body": "Fixed in #303."}]
    },
]

payload = {
    "repo":       "fastapi/fastapi",
    "fetched_at": NOW.isoformat(),
    "items":      items,
}

with open("cache.json", "w") as f:
    json.dump(payload, f, indent=2)

print(f"[test] cache.json written with {len(items)} items.")
