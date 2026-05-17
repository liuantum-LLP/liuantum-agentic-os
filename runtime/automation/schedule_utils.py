from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


MIN_INTERVAL_MINUTES = 15
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def validate_schedule(trigger_type: str, schedule: dict[str, Any] | None, developer_mode: bool = False) -> dict[str, Any]:
    schedule = schedule or {}
    if trigger_type == "manual":
        return {**schedule, "timezone": schedule.get("timezone", "Asia/Kolkata")}
    if trigger_type == "interval":
        minutes = int(schedule.get("interval_minutes") or 0)
        if minutes < MIN_INTERVAL_MINUTES and not developer_mode:
            raise ValueError("Interval automations must be at least 15 minutes in safe mode.")
        return {**schedule, "interval_minutes": minutes, "timezone": schedule.get("timezone", "Asia/Kolkata")}
    if trigger_type in {"daily", "weekly", "monthly"}:
        _parse_time(schedule.get("time_of_day") or "09:00")
    if trigger_type == "weekly":
        days = [str(day).lower() for day in schedule.get("days_of_week", [])]
        if not days or any(day not in WEEKDAYS for day in days):
            raise ValueError("Weekly automations require valid days_of_week.")
        return {**schedule, "days_of_week": days, "timezone": schedule.get("timezone", "Asia/Kolkata")}
    if trigger_type == "monthly":
        day = int(schedule.get("day_of_month") or 1)
        if day < 1 or day > 31:
            raise ValueError("Monthly day_of_month must be between 1 and 31.")
        return {**schedule, "day_of_month": day, "timezone": schedule.get("timezone", "Asia/Kolkata")}
    if trigger_type == "cron_like":
        return {**schedule, "status": "config_ready", "timezone": schedule.get("timezone", "Asia/Kolkata")}
    if trigger_type == "daily":
        return {**schedule, "timezone": schedule.get("timezone", "Asia/Kolkata")}
    raise ValueError(f"Unsupported trigger_type: {trigger_type}")


def calculate_next_run(automation: dict[str, Any], from_time: datetime | None = None) -> str | None:
    if not automation.get("enabled", True):
        return None
    trigger_type = automation.get("trigger_type", "manual")
    schedule = automation.get("schedule") or {}
    current = from_time or now_utc()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if trigger_type == "manual":
        return None
    if trigger_type == "interval":
        minutes = int(schedule.get("interval_minutes") or MIN_INTERVAL_MINUTES)
        last_run = parse_dt(automation.get("last_run_at")) or current
        return (last_run + timedelta(minutes=minutes)).astimezone(timezone.utc).isoformat()
    if trigger_type == "cron_like":
        return None
    tz = _tz(schedule.get("timezone", "Asia/Kolkata"))
    local_now = current.astimezone(tz)
    run_time = _parse_time(schedule.get("time_of_day") or "09:00")
    if trigger_type == "daily":
        candidate = datetime.combine(local_now.date(), run_time, tzinfo=tz)
        if candidate <= local_now:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc).isoformat()
    if trigger_type == "weekly":
        target_days = [WEEKDAYS[day] for day in schedule.get("days_of_week", ["monday"])]
        for offset in range(0, 8):
            day = local_now + timedelta(days=offset)
            if day.weekday() in target_days:
                candidate = datetime.combine(day.date(), run_time, tzinfo=tz)
                if candidate > local_now:
                    return candidate.astimezone(timezone.utc).isoformat()
    if trigger_type == "monthly":
        day = min(int(schedule.get("day_of_month") or 1), 28)
        year, month = local_now.year, local_now.month
        candidate = datetime.combine(local_now.replace(day=day).date(), run_time, tzinfo=tz)
        if candidate <= local_now:
            month += 1
            if month == 13:
                month = 1
                year += 1
            candidate = datetime(year, month, day, run_time.hour, run_time.minute, tzinfo=tz)
        return candidate.astimezone(timezone.utc).isoformat()
    return None


def is_due(automation: dict[str, Any], now: datetime | None = None) -> bool:
    if not automation.get("enabled", True) or automation.get("trigger_type") == "manual":
        return False
    due_at = parse_dt(automation.get("next_run_at"))
    if not due_at:
        return False
    current = now or now_utc()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return due_at <= current


def human_readable_schedule(automation: dict[str, Any]) -> str:
    trigger = automation.get("trigger_type", "manual")
    schedule = automation.get("schedule") or {}
    if trigger == "interval":
        return f"Every {schedule.get('interval_minutes')} minutes"
    if trigger == "daily":
        return f"Daily at {schedule.get('time_of_day', '09:00')} {schedule.get('timezone', 'Asia/Kolkata')}"
    if trigger == "weekly":
        return f"Weekly on {', '.join(schedule.get('days_of_week', []))} at {schedule.get('time_of_day', '09:00')}"
    if trigger == "monthly":
        return f"Monthly on day {schedule.get('day_of_month', 1)} at {schedule.get('time_of_day', '09:00')}"
    if trigger == "cron_like":
        return f"Cron-like schedule stored: {schedule.get('cron_expression', '-')}"
    return "Manual only"


def _parse_time(value: str) -> time:
    hour, minute = [int(part) for part in value.split(":", 1)]
    return time(hour=hour, minute=minute)


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")
