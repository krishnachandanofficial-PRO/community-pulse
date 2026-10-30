# EXPLAIN.md — Krishna's explainer

This file is Krishna's reference for the two metrics he owns and for the
Discord digest code. Every section is written so he can explain it out loud
to a judge in under two minutes.

---

## Metric 3 — Newcomer Retention

**What it measures:**
Among people making their first contribution in our data window, how many
came back with another contribution within 30 days?

**Why it matters:**
A repo that greets newcomers well turns one-time contributors into regulars.
If nobody ever comes back, it signals poor onboarding or unhelpful responses.

**How the code works (line by line in `metrics.py`):**

```python
def newcomer_retention(items, return_window_days=30):
```
- `items` is the list of all 300 issues + PRs from `cache.json`.
- `return_window_days=30` is the default window; can be changed.

**Step 1 — build a timeline per author:**
```python
author_dates: dict[str, list[datetime]] = {}
for item in items:
    login = item["user"]["login"]
    dt    = parse(item["created_at"])
    author_dates[login].append(dt)
```
Result: `{"alice": [Jan 1, Jan 20], "bob": [Jan 5]}` — every time each
person made a contribution, in order.

**Step 2 — define "newcomer":**
In our 300-item snapshot we cannot know a person's full GitHub history.
We approximate: anyone who appears **at most twice** in the snapshot is
treated as a newcomer. (Active maintainers usually appear many times.)

**Step 3 — check retention:**
```python
returned = any(
    0 < (d - first).days <= return_window_days
    for d in dates[1:]
)
```
If the second (or later) contribution is within 30 days of the first, that
person is "retained". 0 < gap means we exclude the same-day duplicate.

**Step 4 — percentage:**
```python
pct = retained / total * 100
```
Example: 40 newcomers, 18 returned within 30 days → retention = 45%.

**Edge cases handled:**
- Bots (login ends with `[bot]`, `-bot`, `bot`) are skipped entirely.
- Items with missing dates are skipped.
- If there are no newcomers at all, we return `None` rather than 0%.

---

## Metric 4 — Contributor Funnel

**What it measures:**
A three-stage funnel showing how contributors progress:

| Stage | Description | Count label |
|-------|-------------|-------------|
| 1 | Opened an issue but no PR | `stage1_issue_only` |
| 2 | Opened at least one PR | `stage2_pr` |
| 3 | Opened more than one contribution (came back) | `stage3_repeat` |

**Why it matters:**
A healthy repo converts issue-reporters into PR contributors and keeps
regulars coming back. A funnel bottleneck at Stage 1→2 suggests the
contribution guide or repo tooling is too hard.

**How the code works:**

```python
for item in items:
    if "pull_request" in item:
        prs_by[login] += 1
    else:
        issues_by[login] += 1
```
`"pull_request" in item` is the official GitHub API way to tell a PR apart
from a plain issue — GitHub returns both from the same `/issues` endpoint.

Then for each unique contributor:
```python
if n_prs == 0:
    stage1_issue_only += 1
else:
    stage2_pr += 1

if total > 1:
    stage3_repeat += 1
```
A person can be in both Stage 2 and Stage 3 (they opened a PR and came
back). That is intentional — it shows progress on the funnel.

---

## The Discord Digest (digest.py)

**What it does in five steps:**

1. **Load** — read `cache.json` (already fetched, no extra API calls needed).
2. **Queue** — sort every open item into one of three queues:
   - ✅ Ready for Review: open PRs with no review yet
   - 🌱 Newcomer Support: first-timer items with no real reply
   - ⚠️ Needs Attention: items blocked by labels like `needs-info`
3. **Score** — each item gets a 0–100 priority score using four factors:
   - Wait time (50%), label priority (25%), newcomer (15%), readiness (10%)
4. **Format** — build a Discord Embed JSON payload with the top 3 items
   per queue, each with a "Next Best Action" recommendation.
5. **Send** — `requests.post(webhook_url, json=payload)` — one HTTP call.

**Priority formula (plain English):**
> score = 0.50 × how_long_waiting + 0.25 × has_important_label
>       + 0.15 × is_newcomer      + 0.10 × is_ready_to_act

Weights are in `WEIGHTS` at the top of `digest.py` and can be changed.

**Test mode:**
```
python digest.py --test
```
Prints everything to the terminal but does NOT call Discord. Use this
to verify the output without spamming the channel.

**Real send:**
```
python digest.py
```
Reads `DISCORD_WEBHOOK_URL` from `.env` and POSTs the message.

---

## Secrets Rule

The Discord webhook URL and GitHub token live **only** in `.env`.
`.env` is in `.gitignore`. They are never pasted in chat, a doc, or the repo.
If you accidentally push a token, GitHub's secret scanner will flag it
within minutes.

---

## Q&A Cheat-Sheet (for judges)

**Q: What is a newcomer in your system?**
A: Someone who appears at most twice in our 300-item snapshot. We can't see
their full GitHub history, so this is a practical approximation.

**Q: Why median and not average for response time?**
A: One very old issue would drag the average up. The median is the middle
value — half are faster, half slower — so one outlier doesn't distort it.

**Q: Why Discord and not WhatsApp?**
A: The problem statement allows Discord, Slack or email. Discord takes one
minute to set up and needs exactly one HTTP POST. WhatsApp needs the
Business API with message template approval.

**Q: Could someone change the weights?**
A: Yes. The `WEIGHTS` dictionary is at the top of `digest.py`. A maintainer
can edit it and rerun the digest.

**Q: What does "Next Best Action" mean?**
A: For every item in the digest we print one clear recommended action:
"Review this PR", "Welcome this newcomer", or "Assign a reviewer now".
The judge never has to decide what to do — the tool tells them.
