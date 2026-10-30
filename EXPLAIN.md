# How fetch.py works

`fetch.py` downloads the newest 300 issues and pull requests (PRs) from one GitHub
repo, along with who replied to them and when, and saves it all to `cache.json`.
Later stages (the dashboard and the Discord digest) only read `cache.json`, so
they never need to talk to GitHub themselves.

The code is split into three small files so each one stays short:

| File | Job |
|---|---|
| `fetch.py` | The main script: decides what to download and in what order. |
| `github_api.py` | Talks to GitHub: the token, the requests, the error messages. |
| `cache_file.py` | Saves, loads and summarises `cache.json`. |
| `metrics.py` | Stage 2: works out wait times and contributor numbers from `cache.json`. |
| `metric_helpers.py` | Small building blocks for `metrics.py` (times, bots, first reply). |
| `report_helpers.py` | Prints the results of `metrics.py`, 3 hand-check samples and a plain-English summary. |
| `data_overview.py` | Shows what's really in `cache.json`: association counts and the date range. |
| `health.py` | Turns the metrics into one 0-100 health score. |
| `health_helpers.py` | The small calculations behind the health score. |

## Running it

```
pip install requests python-dotenv
echo "GITHUB_TOKEN=your_token_here" > .env
python3 fetch.py                    # fastapi/fastapi, uses cache.json if it exists
python3 fetch.py pallets/flask      # a different repo
python3 fetch.py --refresh          # ignore cache.json and download again
```

A full fetch makes about 400 to 600 requests and took about 9 minutes for
fastapi/fastapi. Run it before the demo, not during it.

## The big picture

1. Read the settings (which repo, and whether `--refresh` was passed).
2. If `cache.json` already has this repo and you didn't pass `--refresh`, just print its summary and stop.
3. Otherwise download 3 pages of 100 issues/PRs.
4. For each one, download its comments, and for PRs its reviews too.
5. Save to `cache.json` and print a summary.

## fetch.py

**`read_settings()`** looks at what you typed after `python3 fetch.py`.
`sys.argv` is a list of those words. If a word is `--refresh` we remember that,
and any other word is treated as the repo name. With no words, the repo is
`fastapi/fastapi`. It returns two things: the repo name and `True`/`False` for refresh.

**`fetch_item_list(repo, token)`** downloads the list of issues and PRs. GitHub
returns at most 100 per request ("page"), so we ask for page 1, 2 and 3. We stop
early if a page has fewer than 100 items (the repo has no more), if we already have
300, or if we are nearly out of API calls. It returns the list, how many API calls
GitHub says we have left, and `True` if every page came back fine. GitHub's
"issues" list includes PRs too, which is why one request gets both.

**`describe_user(user)`** pulls out two facts about a person: their login name and
whether the account is a `User` or a `Bot`. If someone deleted their GitHub account,
GitHub sends nothing (`None`), so we call them `"ghost"`, which is what the GitHub
website shows.

**`simplify_item(raw)`** GitHub sends dozens of fields per issue. This keeps only
the ones we need: number, title, whether it's a PR, the author, their
`author_association` (for example `NONE` or `FIRST_TIME_CONTRIBUTOR` for newcomers,
or `MEMBER` for maintainers), when it was created, open/closed state, and whether a
PR is a draft. An item is a PR if GitHub included a `pull_request` field in it.
It also starts two empty lists, `comments` and `reviews`, to be filled in next.

**`fetch_replies(repo, token, raw, calls_left)`** fills in those two lists for one
item. GitHub tells us how many comments an item has, so we only ask for comments
when that number is above 0, which saves requests. For PRs we always ask for reviews,
because the comment count doesn't include them. For each comment we keep who wrote it,
whether they're a bot and when. For each review we also keep its state (`APPROVED`,
`CHANGES_REQUESTED`, `COMMENTED`). If a request fails it returns `None`, so
`main` knows to stop.

**`main()`** runs the steps in order. In the reply loop it checks `calls_left`
before each item. GitHub allows 5,000 calls an hour, and if fewer than 20 are left
we stop cleanly instead of crashing, then save what we have. Every 25 items it prints
progress. At the end it builds the dictionary we save: the repo name, when we
fetched, a `complete` flag (`False` if we stopped early) and the list of items.
Items that never got their replies downloaded are left out on purpose. Otherwise
they would look like "nobody replied", which would make the numbers look worse than
they really are.

## github_api.py

**`read_token()`** uses `python-dotenv` to load the `.env` file, then reads
`GITHUB_TOKEN`. If it's missing, it prints how to fix that and exits. The token is
only ever put into the request header. It is never printed or saved, and `.env` is
listed in `.gitignore` so it can't be committed by accident.

**`explain_error(status_code)`** turns GitHub's error numbers into plain words:
401 means a bad token, 403 means rate limited or no access, and 404 means a wrong
repo name.

**`get_json(path, token)`** is the only place we contact GitHub, and it only ever
does GET (read) requests. It waits 0.1 seconds first so we don't hammer GitHub, then
sends the request with our token. On success it returns the data and the
`X-RateLimit-Remaining` header (how many calls we have left this hour). On any
failure it prints the plain-English reason and returns `None`.

## cache_file.py

**`cache_exists()`**, **`load_cache()`** and **`save_cache(cache)`** check for,
read and write `cache.json`. `indent=2` makes the file readable by people too.

**`has_reply(item)`** answers "did a real person other than the author respond?"
It returns `True` if any comment or review came from a human who isn't the author.
Bots don't count: many repos have a bot that comments on every new PR within
seconds, which would make response times look instant when they aren't.

**`print_summary(cache)`** counts issues, PRs and items with a human reply, then
prints them. If the fetch stopped early, it says so.

## What's in cache.json

```json
{
  "repo": "fastapi/fastapi",
  "fetched_at": "2026-10-30T23:45:00+00:00",
  "complete": true,
  "items": [
    {
      "number": 16634, "title": "...", "is_pr": true,
      "author": "someone", "author_association": "NONE",
      "created_at": "2026-10-30T17:03:57Z", "state": "open", "draft": false,
      "comments": [{"login": "github-actions[bot]", "user_type": "Bot", "created_at": "..."}],
      "reviews": [{"login": "a-maintainer", "user_type": "User", "state": "APPROVED", "submitted_at": "..."}]
    }
  ]
}
```

---

# Stage 2: how metrics.py works

`metrics.py` reads `cache.json` and turns it into numbers. It makes **no** network
calls, so it runs instantly and works offline. Run it with `python3 metrics.py`
after `fetch.py` has made `cache.json`.

## Words we use

- **Human:** any account whose type isn't `Bot` and whose login doesn't end in `[bot]`.
  Bots like `github-actions[bot]` reply within seconds, so counting them would make
  waits look much shorter than they are.
- **Author:** the person who opened the issue or PR. Their own comments don't count as a reply.
- **Hours:** every timestamp is in UTC (the `Z` at the end means UTC). We subtract
  two timestamps and divide the seconds by 3600.
- **Still waiting:** an **open** item with no answer yet. We don't throw these away.
  We count them and list them with how old they are, because throwing them away would
  hide the worst waits. A **closed** item that never got a reply isn't waiting for
  anyone, so it's left out of both the waits and the still-waiting count.
- **Bot-opened items are left out of every metric.** In fastapi, `pr-submit[bot]`
  and `dependabot[bot]` opened 97 of the 300 items. They aren't newcomers, and
  including them would distort the numbers.

## metrics.py

**`first_response_hours(item)`** finds the first comment on an issue or PR from a
human who isn't the author, and returns how many hours after the item was opened
that comment came. If there's no such comment, it returns `None`, which means
"still waiting".

**`pr_review_wait_hours(item)`** does the same for PR reviews. It looks for the first
review from a human who isn't the author, in any state except `PENDING` (a pending
review is one that hasn't been submitted yet). It skips issues and draft PRs, because
a draft says "not ready for review yet". If there's no such review, it returns `None`.

**`median_first_response(items)`** runs `first_response_hours` on every human-opened
item and gives back three numbers: the **median** (the middle value when all the
waits are sorted), how many items were counted, and how many open items are still
waiting. Closed items with no reply are skipped. We use the median rather than the
average because one item that waited 60 days would drag the average way up.

**`median_review_wait(items)`** does the same with `pr_review_wait_hours`, but only
over PRs that aren't drafts.

**`still_waiting_list(items)`** lists every **open**, human-opened item that has no
human reply, plus every open non-draft PR with no human review. Each entry has the
number, title, author, whether it's a PR, and its age in hours (now minus when it
was opened). The list is sorted so the longest wait comes first.

**`newcomer_retention(items)`** is a **draft definition**. A newcomer is a human
(bot authors are excluded) whose `author_association` is `FIRST_TIME_CONTRIBUTOR`,
`FIRST_TIMER` or `NONE`. `NONE` means GitHub sees no link between that person and the
repo: they have no merged commits there and aren't a member. For each newcomer, we
check if they opened another issue or PR within 30 days of their first one. It returns
how many newcomers there are, how many came back, and the percentage. It only looks at
the items in the cache, not the repo's full history.

Why `NONE` is included: on fastapi, the cache only contains `NONE` (134 items),
`CONTRIBUTOR` (101) and `MEMBER` (65), and never `FIRST_TIME_CONTRIBUTOR` or
`FIRST_TIMER`. With only those two, this found 0 newcomers. With `NONE` added, it
finds 97 newcomers, and 19 of them (19.6%) came back. Two limits to mention to judges:
`NONE` can also include an outsider who has opened issues for years without a merged
commit, and the cache only covers 70.5 days. 30 of the 97 newcomers opened their first
item less than 30 days before the newest item, so they haven't had a full 30 days to
come back yet. The real return rate is probably a bit higher.

**`contributor_funnel(items)`** counts different people at three stages: how many
opened at least one issue, how many opened at least one PR, and how many opened two
or more items in total (repeat contributors). It uses a Python `set`, which is like
a list that ignores duplicates, so each person is only counted once.

**`main()`** loads `cache.json` (or tells you to run `fetch.py` first), works out
every metric, puts the results in one dictionary, and hands it to `print_report`.

## metric_helpers.py

**`parse_time(text)`** turns a GitHub timestamp like `2026-10-28T09:15:00Z` into a
Python `datetime`, so we can subtract two of them.

**`hours_between(start, end)`** subtracts two timestamps and gives back hours.
**`hours_since(start)`** does the same, but uses "right now" as the end.

**`is_human(login, user_type)`** returns `False` for bots and `True` for everyone else,
using the definition above.

**`human_authored(items)`** gives back a new list with the bot-opened items removed.
Every metric starts by calling it. We only store the author's login, not their account
type, so for authors we spot bots by the `[bot]` at the end of the login.

**`is_waiting(item)`** returns `True` if the item is still open. It's one line, but
giving it a name makes the rule "only open items can be waiting" easy to find and
change.

**`first_reply_time(item)`** goes through the item's comments, skips the author's own
and any bots, and remembers the earliest one. **`first_review_time(item)`** does the
same for reviews, and also skips `PENDING` ones.

**`summarise_waits(waits)`** takes a list where each value is either a number of hours
or `None`. It splits them into "counted" and "still waiting" and works out the median.
Both median functions use it, so the logic is written only once.

**`get_age(entry)`** just returns an entry's age. Python's `sort` uses it to know what
to sort the still-waiting list by.

**`came_back(items, author, days)`** gathers all the times one author opened something,
sorts them, and checks if any later one is within `days` days of the first.

## report_helpers.py

**`format_hours(hours)`** shows hours as text such as `7.3 h (0.3 days)`, or `n/a` if
there's no value.

**`kind_name(is_pr)`** gives back `"PR"` or `"Issue"`.

**`pick_samples(items)`** picks three human-opened items worth checking by hand: an
issue that got a reply, a PR that got a review, and an open item with no human reply yet.

**`print_sample(item, repo)`** prints one item in detail: a link to open on GitHub, when
it was created, the first human reply time and review time, and the hours each one
took. Open the link and compare the times yourself to confirm the code is right.

**`print_median(label, summary)`** prints one median line: the median, how many items
were counted, and how many are still waiting.

**`print_plain_summary(results)`** prints the main numbers as plain-English sentences,
such as "Of the items that got a human reply, half got one within 6.9 h". These are
ready to read out to judges.

**`print_report(cache, results)`** prints everything in order: first the data overview
(from `data_overview.py`), then the metrics, the 5 longest-waiting items, newcomers
and the funnel, the 3 hand-check samples, and finally the plain-English summary.

## data_overview.py

This file doesn't measure anything. It shows what the data really contains, so we can
check our definitions make sense before trusting the numbers.

**`association_counts(items)`** counts how many items have each `author_association`
value, such as `NONE: 134`. It counts all items, bots included, because it's
describing the raw data. This is how we found out fastapi never uses
`FIRST_TIME_CONTRIBUTOR`.

**`date_range(items)`** finds the oldest and newest `created_at` in the cache, and
how many days apart they are. This tells you how much history the 300 items cover.
For a busy repo it might be a few weeks, and for a quiet one it might be years.

**`print_overview(items)`** prints both of the above at the top of the report.


---

# health.py: the health score

Run `python3 health.py` to get one number from 0 to 100, plus the four parts it's made
of. It uses the functions in `metrics.py`, so the same rules apply: bot-opened items are
left out, and only open items count as still waiting. Every number in the formula is a
named constant at the top of `health.py`, so changing a weight or a threshold means
changing one line.

## The formula

| Part | Points | Full marks | 0 points |
|---|---|---|---|
| Response: median first human reply | 30 | 24 hours or less | 168 hours (7 days) or more |
| Review: median first human PR review | 20 | 48 hours or less | 336 hours (14 days) or more |
| Newcomer: newcomer items waiting over 7 days | 25 | none of them | all of them |
| Unanswered: open items nobody has answered | 25 | none of them | all of them |

**Response and review parts.** In between full marks and 0, the points fall in a
straight line. For example, a median first response of 96 hours is exactly halfway
between 24 and 168, so it gets half of 30, which is 15 points.

**Newcomer part.** We look at every item opened by a newcomer (`FIRST_TIME_CONTRIBUTOR`,
`FIRST_TIMER` or `NONE`, bots excluded) and work out what share of them are still open
with no reply or review after more than 7 days. The part is worth `25 x (1 - that share)`.

**Unanswered part.** We look at every **open** item opened by a human and work out what
share of them have had **no human reply and no human review at all**. The part is worth
`25 x (1 - that share)`. So if half the open items have been ignored, this part gets 12.5.

**Missing data.** If a part can't be worked out (for example, no PR ever got a review,
or there are no open items), it gets **half marks**. That way, missing data doesn't
make a repo look perfect or terrible.

## Why unanswered items now count

The first version only used medians, and a median only looks at items that **did** get
an answer. If a repo answered 10 items quickly and ignored 90, the median would still be
fast and the score would still look great. That's the opposite of what Community Pulse is
for. The unanswered part fixes this by asking a second question: "of the items that are
open right now, how many has nobody answered?" Ignoring people now lowers the score,
even when the answers that did happen were fast.

## The functions

**`health_parts(items)`** (in `health.py`) works out the four parts. **`health_score(items)`**
adds them up and rounds to one decimal place. **`print_part(label, points, max_points)`**
prints one line like `Review part: 20 / 20`. **`main()`** prints the four parts and the total.

In `health_helpers.py`:

**`sliding_points(hours, full_hours, zero_hours, max_points)`** does the straight-line rule
for the response and review parts, and gives half marks when there's no data.

**`share_points(share, max_points)`** does the "max points x (1 - share)" rule for the
newcomer and unanswered parts. It keeps the answer between 0 and the max, and gives half
marks when there's no data.

**`newcomer_long_wait_share(items, wait_hours)`** finds the share of newcomer items that are
on the still-waiting list and older than `wait_hours`.

**`unanswered_share(items)`** counts the open, human-opened items, counts how many of them
have no human reply and no human review, and divides the two.

## fastapi/fastapi example

```
  Response part:   30 / 30     (median 6.9 h, under 24 h)
  Review part:     20 / 20     (median 24.7 h, under 48 h)
  Newcomer part:   23.9 / 25   (3 of 67 newcomer items stuck for 7+ days)
  Unanswered part: 13.3 / 25   (7 of 15 open items have no human answer at all)
Health score: 87.2 / 100
```

The score went from 98.7 to 87.2. Fastapi answers quickly when it answers, but almost half
of its open items haven't had any human answer yet.

**Limits to mention to judges:** only 15 items are open, so a few items can move the
unanswered part a lot. Items that were **closed** without any human reply still don't count
against the score, because the unanswered part only looks at open items.
