"""Booking slot generation.

Given a business profile, this module produces concrete future slots that
respect opening hours, slot length, lead time, and the booking horizon. The
logic is fully deterministic and runs with no external dependencies.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from app.config import BusinessProfile

_WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def _parse_hhmm(value: str) -> time:
    """Parse an ``HH:MM`` string into a :class:`datetime.time`."""
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def suggest_slots(
    profile: BusinessProfile,
    now: datetime | None = None,
) -> list[str]:
    """Generate concrete bookable slots for the business.

    Walks forward day by day within the booking horizon, skipping closed days
    and any time earlier than the configured lead time, and returns ISO 8601
    datetime strings up to ``max_suggestions``.

    Args:
        profile: The validated business profile.
        now: Reference time. Defaults to the current local time. Injectable for
            deterministic tests.

    Returns:
        A list of ISO formatted datetime strings, possibly empty.
    """
    rules = profile.booking_rules
    current = now or datetime.now()
    earliest = current + timedelta(hours=rules.lead_time_hours)
    step = timedelta(minutes=rules.slot_minutes)

    suggestions: list[str] = []

    for day_offset in range(rules.horizon_days + 1):
        day = (current + timedelta(days=day_offset)).date()
        weekday_name = _WEEKDAYS[day.weekday()]
        hours = profile.opening_hours.get(weekday_name)
        if hours is None:
            continue

        open_at = datetime.combine(day, _parse_hhmm(hours.open))
        close_at = datetime.combine(day, _parse_hhmm(hours.close))
        slot = open_at

        while slot + step <= close_at:
            if slot >= earliest:
                suggestions.append(slot.isoformat())
                if len(suggestions) >= rules.max_suggestions:
                    return suggestions
            slot += step

    return suggestions
