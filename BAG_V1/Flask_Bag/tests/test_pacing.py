from datetime import date
from app.pacing import compute_pace, safe_to_spend, runout_week_projection

def test_safe_to_spend():
    assert abs(safe_to_spend(remaining=1600, week_now=1, weeks_total=16) - 100) < 1e-6
    assert abs(safe_to_spend(remaining=1500, week_now=6, weeks_total=16) - (1500/11)) < 1e-6

def test_compute_pace_basic():
    today = date(2026, 2, 28)
    res = compute_pace(
        start_iso="2026-01-05",
        end_iso="2026-04-27",
        weeks_total=16,
        today=today,
        funds_spent=400,
        total_funds=1600
    )
    assert 1 <= res.week_now <= 16
    assert 0 <= res.semester_elapsed_pct <= 100
    assert 0 <= res.funds_spent_pct <= 100

def test_runout_projection_none_when_no_spend():
    assert runout_week_projection(remaining=1000, spent_so_far=0, week_now=4) is None

def test_runout_projection_value():
    # if spent_so_far is 300 over 3 weeks elapsed (week_now=4), avg=100/week
    # remaining=500 => 5 weeks until zero => projected ~ week 9
    assert runout_week_projection(remaining=500, spent_so_far=300, week_now=4) == 9
