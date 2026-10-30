# health_helpers.py - The small calculations behind health.py.
# Each one turns the data into a number that health.py then turns into points.

from metric_helpers import first_reply_time, first_review_time, human_authored, is_waiting
from metrics import NEWCOMER_TYPES, still_waiting_list


# Gives points that fall in a straight line from full marks to 0 as the wait grows.
# In: median hours (or None if no data), full-marks hours, zero hours, most points.
# Out: points. No data gives half marks.
def sliding_points(hours, full_hours, zero_hours, max_points):
    if hours is None:
        return max_points / 2
    if hours <= full_hours:
        return max_points
    if hours >= zero_hours:
        return 0
    return max_points * (zero_hours - hours) / (zero_hours - full_hours)


# Turns a "bad share" (0 = nothing bad, 1 = everything bad) into points.
# In: share (or None if no data) and most points. Out: points, kept between 0 and max.
# No data gives half marks.
def share_points(share, max_points):
    if share is None:
        return max_points / 2
    points = max_points * (1 - share)
    return max(0, min(max_points, points))


# Works out what share of newcomer items have been waiting longer than wait_hours.
# In: items and the hours limit. Out: a number from 0 to 1, or None if no newcomer items.
def newcomer_long_wait_share(items, wait_hours):
    newcomer_numbers = []
    for item in human_authored(items):
        if item["author_association"] in NEWCOMER_TYPES:
            newcomer_numbers.append(item["number"])
    if len(newcomer_numbers) == 0:
        return None
    long_waits = 0
    for entry in still_waiting_list(items):
        if entry["number"] in newcomer_numbers and entry["age_hours"] > wait_hours:
            long_waits = long_waits + 1
    return long_waits / len(newcomer_numbers)


# Works out what share of open, human-opened items have had no human reply AND
# no human review yet (nobody has answered at all).
# In: items. Out: a number from 0 to 1, or None if there are no open items.
def unanswered_share(items):
    open_count = 0
    unanswered = 0
    for item in human_authored(items):
        if not is_waiting(item):
            continue
        open_count = open_count + 1
        if first_reply_time(item) is None and first_review_time(item) is None:
            unanswered = unanswered + 1
    if open_count == 0:
        return None
    return unanswered / open_count
