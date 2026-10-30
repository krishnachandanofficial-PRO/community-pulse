# metric_helpers.py - Small building blocks used by metrics.py.
# Reading timestamps, working out hours, spotting bots, and other small jobs.

from datetime import datetime, timedelta, timezone
from statistics import median


# Turns a GitHub timestamp like "2026-10-28T09:15:00Z" into a UTC datetime.
# In: timestamp text. Out: a datetime we can subtract.
# ("Z" means UTC; we swap it for "+00:00" so older Pythons understand it too.)
def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


# Works out how many hours passed between two timestamps.
# In: start and end timestamp text. Out: hours as a decimal number.
def hours_between(start_text, end_text):
    difference = parse_time(end_text) - parse_time(start_text)
    return difference.total_seconds() / 3600


# Works out how many hours ago something happened.
# In: timestamp text. Out: hours from then until now.
def hours_since(start_text):
    difference = datetime.now(timezone.utc) - parse_time(start_text)
    return difference.total_seconds() / 3600


# Decides if an account is a human: not marked "Bot", and login doesn't end in "[bot]".
# In: login and user type (the type can be None if we don't know it). Out: True or False.
def is_human(login, user_type):
    if user_type == "Bot":
        return False
    if login.endswith("[bot]"):
        return False
    return True


# Keeps only items opened by humans, because bot PRs (like dependabot) aren't newcomers.
# In: items. Out: a new list without bot-authored items.
def human_authored(items):
    kept = []
    for item in items:
        if is_human(item["author"], None):
            kept.append(item)
    return kept


# Decides if an item with no answer yet counts as "still waiting": only if it's still open.
# A closed item with no reply isn't waiting for anyone. In: one item. Out: True or False.
def is_waiting(item):
    return item["state"] == "open"


# Finds the first comment by a human who is not the item's author.
# In: one item. Out: that comment's timestamp text, or None if there isn't one.
def first_reply_time(item):
    earliest = None
    for comment in item["comments"]:
        if comment["login"] == item["author"]:
            continue
        if not is_human(comment["login"], comment["user_type"]):
            continue
        if earliest is None or parse_time(comment["created_at"]) < parse_time(earliest):
            earliest = comment["created_at"]
    return earliest


# Finds the first finished review (any state except PENDING) by a human who is not the author.
# In: one PR item. Out: that review's timestamp text, or None if there isn't one.
def first_review_time(item):
    earliest = None
    for review in item["reviews"]:
        if review["state"] == "PENDING" or review["submitted_at"] is None:
            continue
        if review["login"] == item["author"]:
            continue
        if not is_human(review["login"], review["user_type"]):
            continue
        if earliest is None or parse_time(review["submitted_at"]) < parse_time(earliest):
            earliest = review["submitted_at"]
    return earliest


# Turns a list of waits into a summary. None in the list means "still waiting".
# In: list of hours or None. Out: dictionary with median_hours, counted and still_waiting.
def summarise_waits(waits):
    counted = []
    still_waiting = 0
    for hours in waits:
        if hours is None:
            still_waiting = still_waiting + 1
        else:
            counted.append(hours)
    median_hours = None
    if len(counted) > 0:
        median_hours = median(counted)
    return {"median_hours": median_hours, "counted": len(counted), "still_waiting": still_waiting}


# Used for sorting the still-waiting list. In: one waiting entry. Out: its age in hours.
def get_age(entry):
    return entry["age_hours"]


# Checks if an author opened another item within `days` days of their first one in the cache.
# In: items, an author login, number of days. Out: True or False.
def came_back(items, author, days):
    times = []
    for item in items:
        if item["author"] == author:
            times.append(parse_time(item["created_at"]))
    times.sort()
    for later in times[1:]:
        if later - times[0] <= timedelta(days=days):
            return True
    return False
