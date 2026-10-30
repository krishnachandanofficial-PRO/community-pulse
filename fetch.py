"""
fetch.py — owned by Nishanth (backend)
Fetches latest 300 issues + PRs from GitHub API and saves to cache.json.
"""

import os
import json
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO  = os.getenv("GITHUB_REPO", "fastapi/fastapi")
CACHE_FILE   = "cache.json"
FETCH_LIMIT  = 300   # hackathon cap; raise later if needed


def _headers():
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def fetch_items(repo: str = GITHUB_REPO) -> list[dict]:
    """Return up to FETCH_LIMIT issues + PRs from `repo` (newest first)."""
    items = []
    page  = 1
    per   = 100
    while len(items) < FETCH_LIMIT:
        url = (f"https://api.github.com/repos/{repo}/issues"
               f"?state=all&per_page={per}&page={page}")
        resp = requests.get(url, headers=_headers(), timeout=20)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        items.extend(batch)
        page += 1
        if len(batch) < per:
            break
        time.sleep(0.5)   # be polite to the API
    return items[:FETCH_LIMIT]


def fetch_comments(repo: str, number: int) -> list[dict]:
    url  = f"https://api.github.com/repos/{repo}/issues/{number}/comments"
    resp = requests.get(url, headers=_headers(), timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_reviews(repo: str, number: int) -> list[dict]:
    url  = f"https://api.github.com/repos/{repo}/pulls/{number}/reviews"
    resp = requests.get(url, headers=_headers(), timeout=20)
    resp.raise_for_status()
    return resp.json()


def run(repo: str = GITHUB_REPO):
    print(f"[fetch] Fetching up to {FETCH_LIMIT} items from {repo} …")
    items = fetch_items(repo)
    print(f"[fetch] Got {len(items)} items. Fetching comments + reviews …")

    enriched = []
    for i, item in enumerate(items, 1):
        num = item["number"]
        is_pr = "pull_request" in item

        comments = []
        reviews  = []
        try:
            comments = fetch_comments(repo, num)
            if is_pr:
                reviews = fetch_reviews(repo, num)
        except Exception as e:
            print(f"  [warn] #{num}: {e}")

        enriched.append({**item, "_comments": comments, "_reviews": reviews})

        if i % 50 == 0:
            print(f"  … {i}/{len(items)}")
        time.sleep(0.1)

    payload = {
        "repo":       repo,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items":      enriched,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[fetch] Saved {len(enriched)} items to {CACHE_FILE}")


if __name__ == "__main__":
    run()
