"""
health.py — owned by Nishanth (backend)

Converts the four metrics into a single 0–100 health score and a
traffic-light grade (A / B / C / D / F).

Formula weights:
  First response time  : 30 %
  PR review wait       : 30 %
  Newcomer retention   : 25 %
  Contributor funnel   : 15 %

Lower waiting time = higher score; higher retention = higher score.
"""

from typing import Optional


# ──────────────────────────────────────────────
# Per-metric sub-scores (each 0–100)
# ──────────────────────────────────────────────

def _score_time(minutes: Optional[float], excellent: float, terrible: float) -> float:
    """
    Linear interpolation: excellent minutes → 100, terrible → 0.
    Anything better than excellent caps at 100; worse than terrible → 0.
    """
    if minutes is None:
        return 50.0   # no data: neutral
    if minutes <= excellent:
        return 100.0
    if minutes >= terrible:
        return 0.0
    return round(100.0 * (terrible - minutes) / (terrible - excellent), 1)


def score_first_response(median_min: Optional[float]) -> float:
    """100 at ≤60 min, 0 at ≥10 080 min (7 days)."""
    return _score_time(median_min, excellent=60, terrible=10_080)


def score_pr_review(median_min: Optional[float]) -> float:
    """100 at ≤120 min (2 h), 0 at ≥20 160 min (14 days)."""
    return _score_time(median_min, excellent=120, terrible=20_160)


def score_newcomer_retention(retention_pct: Optional[float]) -> float:
    """Retention % maps directly to 0–100."""
    if retention_pct is None:
        return 50.0
    return min(100.0, max(0.0, round(retention_pct, 1)))


def score_funnel(funnel: dict) -> float:
    """
    Funnel score = (stage2_pr + stage3_repeat) / total_contributors * 100.
    Rewards repos where issue-raisers go on to submit PRs and come back.
    """
    total = funnel.get("total_contributors", 0)
    if not total:
        return 50.0
    advanced = funnel.get("stage2_pr", 0) + funnel.get("stage3_repeat", 0)
    # cap at total to avoid > 100 (stage3 people are also in stage2)
    raw = min(advanced, total) / total * 100
    return round(raw, 1)


# ──────────────────────────────────────────────
# Composite score
# ──────────────────────────────────────────────

WEIGHTS = {
    "first_response": 0.30,
    "pr_review":      0.30,
    "retention":      0.25,
    "funnel":         0.15,
}


def health_score(metrics: dict) -> dict:
    """
    Takes the output of metrics.all_metrics() and returns:
      score       – 0-100 composite
      grade       – A / B / C / D / F
      breakdown   – per-metric sub-scores with weights
    """
    sub = {
        "first_response": score_first_response(metrics.get("median_first_response_min")),
        "pr_review":      score_pr_review(metrics.get("median_pr_review_wait_min")),
        "retention":      score_newcomer_retention(
                              (metrics.get("newcomer_retention") or {}).get("retention_pct")),
        "funnel":         score_funnel(metrics.get("contributor_funnel") or {}),
    }

    composite = sum(sub[k] * WEIGHTS[k] for k in sub)
    composite = round(composite, 1)

    if composite >= 80:
        grade = "A"
    elif composite >= 65:
        grade = "B"
    elif composite >= 50:
        grade = "C"
    elif composite >= 35:
        grade = "D"
    else:
        grade = "F"

    return {
        "score":     composite,
        "grade":     grade,
        "breakdown": {
            k: {"sub_score": sub[k], "weight": WEIGHTS[k]}
            for k in sub
        },
    }


if __name__ == "__main__":
    import pprint
    from metrics import all_metrics
    m = all_metrics()
    pprint.pprint(health_score(m))
