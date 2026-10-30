# fetch.py - Stage 1 of Community Pulse.
# Downloads the latest 300 issues and PRs from a GitHub repo, plus their
# comments and reviews, and saves them to cache.json.
# Usage: python3 fetch.py [owner/repo] [--refresh]

import sys
from datetime import datetime, timezone

from cache_file import cache_exists, load_cache, print_summary, save_cache
from github_api import get_json, read_token

DEFAULT_REPO = "fastapi/fastapi"
MAX_ITEMS = 300
PAGES = 3
LOW_RATE_LIMIT = 20  # stop when GitHub says fewer calls than this are left


# Reads the command line. In: nothing. Out: repo name, and True/False for --refresh.
def read_settings():
    repo = DEFAULT_REPO
    refresh = False
    for arg in sys.argv[1:]:
        if arg == "--refresh":
            refresh = True
        else:
            repo = arg
    return repo, refresh


# Gets the newest issues and PRs, up to 3 pages of 100.
# In: repo and token. Out: list of raw items, calls left, and True if nothing went wrong.
def fetch_item_list(repo, token):
    items = []
    calls_left = 5000
    for page in range(1, PAGES + 1):
        path = "/repos/" + repo + "/issues?state=all&per_page=100&page=" + str(page)
        data, calls_left = get_json(path + "&sort=created&direction=desc", token)
        if data is None:
            return items, calls_left, False
        items.extend(data)
        print("Fetched page " + str(page) + " of " + str(PAGES))
        if len(data) < 100 or len(items) >= MAX_ITEMS or calls_left < LOW_RATE_LIMIT:
            break
    return items[:MAX_ITEMS], calls_left, calls_left >= LOW_RATE_LIMIT


# Gets the login name and account type (User or Bot) of a GitHub user.
# In: user data (empty for deleted accounts). Out: login and type.
def describe_user(user):
    if user is None:
        return "ghost", "User"
    return user["login"], user["type"]


# Keeps only the fields we need from one issue or PR. In: raw item. Out: small dictionary.
# An item is a PR if GitHub gave it a "pull_request" field.
def simplify_item(raw):
    login, user_type = describe_user(raw["user"])
    return {"number": raw["number"], "title": raw["title"],
            "is_pr": "pull_request" in raw, "author": login,
            "author_association": raw["author_association"],
            "created_at": raw["created_at"], "state": raw["state"],
            "draft": raw.get("draft", False), "comments": [], "reviews": []}


# Fetches the comments (and reviews, for PRs) of one item.
# In: repo, token, raw item. Out: simplified item (None if a call failed) and calls left.
def fetch_replies(repo, token, raw, calls_left):
    item = simplify_item(raw)
    number = str(item["number"])
    if raw["comments"] > 0:
        data, calls_left = get_json("/repos/" + repo + "/issues/" + number + "/comments?per_page=100", token)
        if data is None:
            return None, calls_left
        for comment in data:
            login, user_type = describe_user(comment["user"])
            item["comments"].append({"login": login, "user_type": user_type,
                                     "created_at": comment["created_at"]})
    if item["is_pr"]:
        data, calls_left = get_json("/repos/" + repo + "/pulls/" + number + "/reviews?per_page=100", token)
        if data is None:
            return None, calls_left
        for review in data:
            login, user_type = describe_user(review["user"])
            item["reviews"].append({"login": login, "user_type": user_type,
                                    "state": review["state"], "submitted_at": review.get("submitted_at")})
    return item, calls_left


# Runs every step: use the cache if we can, otherwise fetch, save, and summarise.
def main():
    repo, refresh = read_settings()
    if cache_exists() and not refresh:
        cache = load_cache()
        if cache["repo"] == repo:
            print("Using saved cache.json (run with --refresh to fetch again).")
            print_summary(cache)
            return
        print("cache.json is for " + cache["repo"] + ", so fetching " + repo + " instead.")
    token = read_token()
    raw_items, calls_left, complete = fetch_item_list(repo, token)
    if len(raw_items) == 0:
        print("Nothing was fetched, so nothing was saved.")
        sys.exit(1)
    items = []
    for raw in raw_items:
        if calls_left < LOW_RATE_LIMIT:
            print("Rate limit almost used up. Stopping early and saving what we have.")
            break
        item, calls_left = fetch_replies(repo, token, raw, calls_left)
        if item is None:
            print("Stopping early and saving what we have.")
            break
        items.append(item)
        if len(items) % 25 == 0 or len(items) == len(raw_items):
            print("Fetched replies for " + str(len(items)) + " of " + str(len(raw_items)))
    cache = {"repo": repo, "fetched_at": datetime.now(timezone.utc).isoformat(),
             "complete": complete and len(items) == len(raw_items), "items": items}
    save_cache(cache)
    print_summary(cache)


if __name__ == "__main__":
    main()
