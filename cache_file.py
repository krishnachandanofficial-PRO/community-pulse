# cache_file.py - Saving, loading and summarising cache.json.
# Later stages (dashboard, digest) can import load_cache from here too.

import json
import os

CACHE_FILE = "cache.json"


# Checks whether cache.json exists. In: nothing. Out: True or False.
def cache_exists():
    return os.path.exists(CACHE_FILE)


# Reads cache.json. In: nothing. Out: the saved data as a dictionary.
def load_cache():
    with open(CACHE_FILE) as file:
        return json.load(file)


# Writes data to cache.json, nicely indented. In: dictionary. Out: nothing.
def save_cache(cache):
    with open(CACHE_FILE, "w") as file:
        json.dump(cache, file, indent=2)
    print("Saved to " + CACHE_FILE)


# Checks if a human other than the author commented or reviewed (bots don't count).
# In: one item. Out: True or False.
def has_reply(item):
    for person in item["comments"] + item["reviews"]:
        if person["login"] != item["author"] and person["user_type"] != "Bot":
            return True
    return False


# Prints the totals. In: the cache dictionary. Out: nothing.
def print_summary(cache):
    items = cache["items"]
    pr_count = 0
    reply_count = 0
    for item in items:
        if item["is_pr"]:
            pr_count = pr_count + 1
        if has_reply(item):
            reply_count = reply_count + 1
    print("")
    print("Summary for " + cache["repo"])
    print("  Total items: " + str(len(items)))
    print("  Issues: " + str(len(items) - pr_count))
    print("  PRs: " + str(pr_count))
    print("  With a reply from a human other than the author: " + str(reply_count))
    if not cache["complete"]:
        print("  Note: the fetch stopped early, so this data is incomplete.")
