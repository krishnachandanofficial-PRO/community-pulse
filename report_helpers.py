# report_helpers.py - Printing for the main section of metrics.py.
# Formats hours, prints the results, and prints sample items to check by hand on GitHub.

from data_overview import print_overview
from metric_helpers import first_reply_time, first_review_time, hours_between, human_authored, is_waiting


# Shows hours as text. In: hours or None. Out: e.g. "12.3 h (0.5 days)", or "n/a".
def format_hours(hours):
    if hours is None:
        return "n/a"
    return str(round(hours, 1)) + " h (" + str(round(hours / 24, 1)) + " days)"


# Gives a readable name for an item. In: True/False for is_pr. Out: "PR" or "Issue".
def kind_name(is_pr):
    if is_pr:
        return "PR"
    return "Issue"


# Picks 3 human-authored items worth checking: an issue with a reply, a PR with a
# review, and an open item with no human reply yet. In: items. Out: list of up to 3 items.
def pick_samples(items):
    issue_with_reply = None
    pr_with_review = None
    no_reply = None
    for item in human_authored(items):
        if issue_with_reply is None and not item["is_pr"] and first_reply_time(item) is not None:
            issue_with_reply = item
        if pr_with_review is None and item["is_pr"] and first_review_time(item) is not None:
            pr_with_review = item
        if no_reply is None and is_waiting(item) and first_reply_time(item) is None:
            no_reply = item
    samples = []
    for item in [issue_with_reply, pr_with_review, no_reply]:
        if item is not None:
            samples.append(item)
    return samples


# Prints one item in detail with a link, so it can be compared with GitHub in a browser.
# In: one item and the repo name. Out: nothing (it prints).
def print_sample(item, repo):
    print("")
    print(kind_name(item["is_pr"]) + " #" + str(item["number"]) + " by " + item["author"])
    print("  Link:        https://github.com/" + repo + "/issues/" + str(item["number"]))
    print("  Created:     " + item["created_at"])
    reply_time = first_reply_time(item)
    if reply_time is None:
        print("  First human reply: none yet")
    else:
        print("  First human reply: " + reply_time + "  ->  " + format_hours(hours_between(item["created_at"], reply_time)))
    if item["is_pr"]:
        review_time = first_review_time(item)
        if item["draft"]:
            print("  First human review: skipped (draft PR)")
        elif review_time is None:
            print("  First human review: none yet")
        else:
            print("  First human review: " + review_time + "  ->  " + format_hours(hours_between(item["created_at"], review_time)))


# Prints a median summary on one line. In: a label and a summary dictionary. Out: nothing.
def print_median(label, summary):
    print(label + format_hours(summary["median_hours"]) + ", counted "
          + str(summary["counted"]) + ", still waiting " + str(summary["still_waiting"]))


# Prints the main numbers as plain-English sentences. In: results dictionary. Out: nothing.
def print_plain_summary(results):
    retention = results["retention"]
    waiting = results["waiting"]
    print("")
    print("In plain English:")
    print("- Of the items that got a human reply, half got one within "
          + format_hours(results["first"]["median_hours"]) + ".")
    print("- Of the PRs that got a human review, half got one within "
          + format_hours(results["review"]["median_hours"]) + ".")
    print("- " + str(len(waiting)) + " open items are still waiting for a reply or review.")
    if len(waiting) > 0:
        print("  The longest has waited " + format_hours(waiting[0]["age_hours"]) + ".")
    print("- " + str(retention["came_back"]) + " of " + str(retention["newcomers"]) + " newcomers ("
          + str(retention["percent"]) + "%) opened something else within 30 days.")


# Prints what the data contains, everything metrics.py worked out, 3 samples to check
# by hand, and a plain-English summary.
# In: the cache dictionary, and the results dictionary from metrics.py. Out: nothing.
def print_report(cache, results):
    print_overview(cache["items"])
    print("Metrics for " + cache["repo"] + " (" + str(len(cache["items"])) + " items, "
          + str(len(human_authored(cache["items"]))) + " opened by humans; bot-opened items are left out)")
    print_median("Median first response: ", results["first"])
    print_median("Median PR review wait: ", results["review"])
    waiting = results["waiting"]
    print("Still waiting (open, with no reply or PR with no review): " + str(len(waiting)) + ". Longest 5:")
    for entry in waiting[:5]:
        print("  #" + str(entry["number"]) + " " + kind_name(entry["is_pr"]) + " by " + entry["author"]
              + ", " + format_hours(entry["age_hours"]) + ": " + entry["title"][:60])
    retention = results["retention"]
    print("Newcomers (FIRST_TIME_CONTRIBUTOR, FIRST_TIMER or NONE; bots excluded): "
          + str(retention["newcomers"]))
    print("  Opened another issue or PR within 30 days of their first: " + str(retention["came_back"])
          + " (" + str(retention["percent"]) + "%)  [draft definition]")
    funnel = results["funnel"]
    print("Funnel: opened an issue " + str(funnel["opened_issue"]) + ", opened a PR "
          + str(funnel["opened_pr"]) + ", repeat contributors " + str(funnel["repeat"]))
    print("")
    print("Three samples to check by hand on GitHub:")
    for item in pick_samples(cache["items"]):
        print_sample(item, cache["repo"])
    print_plain_summary(results)
