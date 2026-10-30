# metrics.py - Stage 2 of Community Pulse. Usage: python3 metrics.py
# Works out response times and contributor numbers from cache.json (no network calls).
# Items opened by bots are left out everywhere, because bots aren't newcomers.

import sys

from cache_file import cache_exists, load_cache
from metric_helpers import (came_back, first_reply_time, first_review_time, get_age,
                            hours_between, hours_since, human_authored, is_waiting,
                            summarise_waits)
from report_helpers import print_report

# NONE = GitHub has no link between this person and the repo (no merged commits, not a member).
NEWCOMER_TYPES = ["FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"]
RETENTION_DAYS = 30


# 1. Hours from when an item was opened to the first comment by a human who isn't the author.
# In: one item (issue or PR). Out: hours, or None if no such comment yet.
def first_response_hours(item):
    reply_time = first_reply_time(item)
    if reply_time is None:
        return None
    return hours_between(item["created_at"], reply_time)


# 2. Hours from when a PR was opened to its first review by a human who isn't the author.
# In: one item. Out: hours, or None if it's not a PR, is a draft, or has no such review yet.
def pr_review_wait_hours(item):
    if not item["is_pr"] or item["draft"]:
        return None
    review_time = first_review_time(item)
    if review_time is None:
        return None
    return hours_between(item["created_at"], review_time)


# 3a. Median first-response time. Closed items with no reply are left out (not waiting).
# In: items. Out: dictionary with median_hours, counted and still_waiting.
def median_first_response(items):
    waits = []
    for item in human_authored(items):
        hours = first_response_hours(item)
        if hours is not None or is_waiting(item):
            waits.append(hours)
    return summarise_waits(waits)


# 3b. Median review wait over non-draft PRs. Closed PRs with no review are left out.
# In: items. Out: dictionary with median_hours, counted and still_waiting.
def median_review_wait(items):
    waits = []
    for item in human_authored(items):
        if item["is_pr"] and not item["draft"]:
            hours = pr_review_wait_hours(item)
            if hours is not None or is_waiting(item):
                waits.append(hours)
    return summarise_waits(waits)


# 4. Open items with no human reply, or non-draft PRs with no human review, longest first.
# In: items. Out: list of dictionaries with number, title, author, is_pr, age_hours.
def still_waiting_list(items):
    waiting = []
    for item in human_authored(items):
        no_reply = first_reply_time(item) is None
        no_review = item["is_pr"] and not item["draft"] and first_review_time(item) is None
        if is_waiting(item) and (no_reply or no_review):
            waiting.append({"number": item["number"], "title": item["title"],
                            "author": item["author"], "is_pr": item["is_pr"],
                            "age_hours": hours_since(item["created_at"])})
    waiting.sort(key=get_age, reverse=True)
    return waiting


# 5. DRAFT definition, limited to the items in the cache (not the repo's full history):
# authors whose first item is near the newest end haven't had a full 30 days yet.
# A newcomer is an author with association FIRST_TIME_CONTRIBUTOR, FIRST_TIMER or NONE.
# In: items. Out: dictionary with newcomers, came_back and percent (None if no newcomers).
def newcomer_retention(items):
    items = human_authored(items)
    newcomers = []
    for item in items:
        if item["author_association"] in NEWCOMER_TYPES and item["author"] not in newcomers:
            newcomers.append(item["author"])
    returned = 0
    for author in newcomers:
        if came_back(items, author, RETENTION_DAYS):
            returned = returned + 1
    percent = None
    if len(newcomers) > 0:
        percent = round(100 * returned / len(newcomers), 1)
    return {"newcomers": len(newcomers), "came_back": returned, "percent": percent}


# 6. Counts different authors: who opened an issue, who opened a PR, who opened 2+ items.
# In: items. Out: dictionary with opened_issue, opened_pr and repeat.
def contributor_funnel(items):
    issue_authors = set()
    pr_authors = set()
    item_counts = {}
    for item in human_authored(items):
        if item["is_pr"]:
            pr_authors.add(item["author"])
        else:
            issue_authors.add(item["author"])
        item_counts[item["author"]] = item_counts.get(item["author"], 0) + 1
    repeat = 0
    for author in item_counts:
        if item_counts[author] >= 2:
            repeat = repeat + 1
    return {"opened_issue": len(issue_authors), "opened_pr": len(pr_authors), "repeat": repeat}


# Loads cache.json, works out every metric, and prints them (printing is in report_helpers.py).
def main():
    if not cache_exists():
        print("No cache.json yet. Run python3 fetch.py first.")
        sys.exit(1)
    cache = load_cache()
    items = cache["items"]
    results = {"first": median_first_response(items), "review": median_review_wait(items),
               "waiting": still_waiting_list(items), "retention": newcomer_retention(items),
               "funnel": contributor_funnel(items)}
    print_report(cache, results)


if __name__ == "__main__":
    main()
