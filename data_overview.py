# data_overview.py - Describes what is really in cache.json, before any metrics.
# Counts the author_association values and shows which dates the items cover.

from metric_helpers import hours_between, parse_time


# Counts how many items have each author_association value (all items, bots included).
# In: items. Out: dictionary like {"NONE": 134, "MEMBER": 65}.
def association_counts(items):
    counts = {}
    for item in items:
        value = item["author_association"]
        counts[value] = counts.get(value, 0) + 1
    return counts


# Finds the oldest and newest created_at, and how many days apart they are.
# In: items. Out: dictionary with oldest, newest (timestamp text) and days.
def date_range(items):
    oldest = items[0]["created_at"]
    newest = items[0]["created_at"]
    for item in items:
        if parse_time(item["created_at"]) < parse_time(oldest):
            oldest = item["created_at"]
        if parse_time(item["created_at"]) > parse_time(newest):
            newest = item["created_at"]
    days = round(hours_between(oldest, newest) / 24, 1)
    return {"oldest": oldest, "newest": newest, "days": days}


# Prints the association counts and the date range. In: items. Out: nothing (it prints).
def print_overview(items):
    print("What cache.json contains (all " + str(len(items)) + " items, bots included):")
    counts = association_counts(items)
    for value in sorted(counts):
        print("  " + value + ": " + str(counts[value]))
    dates = date_range(items)
    print("  Oldest item: " + dates["oldest"])
    print("  Newest item: " + dates["newest"])
    print("  That covers " + str(dates["days"]) + " days.")
    print("")
