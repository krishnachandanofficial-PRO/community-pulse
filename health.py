# health.py - One 0-100 health score for a repo, built from metrics.py.
# Rule-based: every number used is a named constant below, so it's easy to explain.
# Usage: python3 health.py

import sys

from cache_file import cache_exists, load_cache
from health_helpers import newcomer_long_wait_share, share_points, sliding_points, unanswered_share
from metrics import median_first_response, median_review_wait

RESPONSE_POINTS = 30        # most points for a fast first human reply
RESPONSE_FULL_HOURS = 24    # median at or under this gets full marks
RESPONSE_ZERO_HOURS = 168   # median at or over this (7 days) gets 0
REVIEW_POINTS = 20          # most points for a fast first human PR review
REVIEW_FULL_HOURS = 48
REVIEW_ZERO_HOURS = 336     # 14 days
NEWCOMER_POINTS = 25        # most points for not leaving newcomers waiting
NEWCOMER_WAIT_HOURS = 168   # a newcomer item waiting longer than this (7 days) counts against us
UNANSWERED_POINTS = 25      # most points for having no open items that nobody has answered


# Works out the four parts of the score.
# In: items. Out: dictionary with response, review, newcomer and unanswered points.
def health_parts(items):
    response = sliding_points(median_first_response(items)["median_hours"],
                              RESPONSE_FULL_HOURS, RESPONSE_ZERO_HOURS, RESPONSE_POINTS)
    review = sliding_points(median_review_wait(items)["median_hours"],
                            REVIEW_FULL_HOURS, REVIEW_ZERO_HOURS, REVIEW_POINTS)
    newcomer = share_points(newcomer_long_wait_share(items, NEWCOMER_WAIT_HOURS), NEWCOMER_POINTS)
    unanswered = share_points(unanswered_share(items), UNANSWERED_POINTS)
    return {"response": response, "review": review, "newcomer": newcomer, "unanswered": unanswered}


# The main function: adds up the four parts. In: items. Out: a score from 0 to 100.
def health_score(items):
    parts = health_parts(items)
    total = parts["response"] + parts["review"] + parts["newcomer"] + parts["unanswered"]
    return round(total, 1)


# Prints one part of the score. In: label, points, most points. Out: nothing.
def print_part(label, points, max_points):
    print("  " + label + str(round(points, 1)) + " / " + str(max_points))


# Loads cache.json and prints the four parts and the total.
def main():
    if not cache_exists():
        print("No cache.json yet. Run python3 fetch.py first.")
        sys.exit(1)
    items = load_cache()["items"]
    parts = health_parts(items)
    print_part("Response part:   ", parts["response"], RESPONSE_POINTS)
    print_part("Review part:     ", parts["review"], REVIEW_POINTS)
    print_part("Newcomer part:   ", parts["newcomer"], NEWCOMER_POINTS)
    print_part("Unanswered part: ", parts["unanswered"], UNANSWERED_POINTS)
    print("Health score: " + str(health_score(items)) + " / 100")


if __name__ == "__main__":
    main()
