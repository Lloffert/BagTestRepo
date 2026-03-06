from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from math import ceil

def parse_iso(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()

def weeks_between(start: date, end: date) -> int:
    # semester length in weeks; inclusive-ish for predictable UX
    days = (end - start).days + 1
    return max(1, ceil(days / 7))

def current_week(start: date, today: date, total_weeks: int) -> int:
    if today <= start:
        return 1
    days = (today - start).days
    wk = (days // 7) + 1
    return max(1, min(total_weeks, wk))

def pct(part: float, whole: float) -> float:
    return (part / whole * 100.0) if whole > 0 else 0.0

@dataclass
class PaceResult:
    week_now: int
    weeks_total: int
    semester_elapsed_pct: float
    funds_spent_pct: float
    status: str        # green/yellow/red
    status_text: str
    message: str

def pace_status(semester_elapsed_pct: float, funds_spent_pct: float) -> tuple[str, str]:
    delta = funds_spent_pct - semester_elapsed_pct
    if delta <= 2:
        return ("green", "On track")
    if delta <= 8:
        return ("yellow", "Slightly ahead of pace")
    return ("red", "Over pace")

def teaching_message(week_now: int, weeks_total: int, semester_elapsed_pct: float, funds_spent_pct: float) -> str:
    # supportive, never judgmental
    if funds_spent_pct > semester_elapsed_pct + 10:
        return f"You’ve used {funds_spent_pct:.0f}% of your funds — but we’re only at week {week_now} of {weeks_total}. Let’s recalibrate your weekly spending."
    if abs(funds_spent_pct - semester_elapsed_pct) <= 10:
        return f"You’re pacing well. You’re around week {week_now} of {weeks_total}, and your spending matches the semester pace."
    return f"Nice work — you’re spending below pace for week {week_now}. That gives you more flexibility later in the semester."

def compute_pace(start_iso: str, end_iso: str, weeks_total: int, today: date, funds_spent: float, total_funds: float) -> PaceResult:
    start = parse_iso(start_iso)
    end = parse_iso(end_iso)
    # weeks_total is stored; still clamp week
    wk = current_week(start, today, weeks_total)
    semester_elapsed_pct = (wk / weeks_total) * 100.0
    funds_spent_pct = pct(funds_spent, total_funds)
    status, status_text = pace_status(semester_elapsed_pct, funds_spent_pct)
    msg = teaching_message(wk, weeks_total, semester_elapsed_pct, funds_spent_pct)
    return PaceResult(
        week_now=wk,
        weeks_total=weeks_total,
        semester_elapsed_pct=semester_elapsed_pct,
        funds_spent_pct=funds_spent_pct,
        status=status,
        status_text=status_text,
        message=msg,
    )

def safe_to_spend(remaining: float, week_now: int, weeks_total: int) -> float:
    weeks_left = max(1, weeks_total - week_now + 1)
    return remaining / weeks_left

def runout_week_projection(remaining: float, spent_so_far: float, week_now: int) -> int | None:
    # average weekly spend so far based on completed weeks (week_now-1)
    weeks_elapsed = max(1, week_now - 1)
    avg = spent_so_far / weeks_elapsed if weeks_elapsed > 0 else 0.0
    if avg <= 0:
        return None
    weeks_until_zero = remaining / avg
    # projected run-out is current week + weeks_until_zero
    return int(ceil(week_now + weeks_until_zero))
