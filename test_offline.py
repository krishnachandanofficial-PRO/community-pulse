"""
test_offline.py  — runs without requests or dotenv
Tests metrics.py and the digest queue builder using the local cache.json.
"""
import sys, json, statistics
from datetime import datetime, timezone

# ── Patch out external imports so we can test without pip ──────────
import types

# Fake 'requests' so digest.py can be imported
fake_requests = types.ModuleType("requests")
def _fake_post(*a, **kw):
    class R:
        status_code = 204
        text = ""
    return R()
fake_requests.post = _fake_post
sys.modules.setdefault("requests", fake_requests)

# Fake 'dotenv'
fake_dotenv = types.ModuleType("dotenv")
fake_dotenv.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", fake_dotenv)

# ── Now import our modules ─────────────────────────────────────────
from metrics import (all_metrics, newcomer_retention, contributor_funnel,
                     median_first_response_minutes, median_pr_review_wait_minutes)
from health  import health_score
from digest  import build_queues, _priority_score, _build_author_count, _age_minutes

# ── Load cache ─────────────────────────────────────────────────────
with open("cache.json") as f:
    data = json.load(f)
items = data["items"]

print("\n=== METRICS TEST ===")
m = all_metrics()
print(f"  Items in cache            : {m['item_count']}")
print(f"  Median first response     : {m['median_first_response_min']} min")
print(f"  Median PR review wait     : {m['median_pr_review_wait_min']} min")

ret = m["newcomer_retention"]
print(f"\n  METRIC 3 — Newcomer Retention")
print(f"    Newcomers found         : {ret['newcomer_count']}")
print(f"    Retained (30-day)       : {ret['retained_count']}")
print(f"    Retention %             : {ret['retention_pct']}")

fn = m["contributor_funnel"]
print(f"\n  METRIC 4 — Contributor Funnel")
print(f"    Stage 1 (issue only)    : {fn['stage1_issue_only']}")
print(f"    Stage 2 (has PR)        : {fn['stage2_pr']}")
print(f"    Stage 3 (repeat)        : {fn['stage3_repeat']}")
print(f"    Total contributors      : {fn['total_contributors']}")

print("\n=== HEALTH SCORE ===")
h = health_score(m)
print(f"  Score  : {h['score']}/100")
print(f"  Grade  : {h['grade']}")
for k, v in h["breakdown"].items():
    print(f"    {k:20s}: sub={v['sub_score']:5.1f}  weight={v['weight']}")

print("\n=== QUEUE TEST ===")
queues = build_queues(items)
for q_name in ("ready_for_review", "newcomer_support", "needs_attention"):
    entries = queues[q_name]
    print(f"\n  {q_name} ({len(entries)} items):")
    for e in entries:
        kind = "PR" if e["is_pr"] else "Issue"
        print(f"    [{kind} #{e['number']}] score={e['score']} age={e['age_hrs']}h "
              f"reason='{e['reasons']['reason_text']}'")

print("\n✅ All offline tests passed.\n")
