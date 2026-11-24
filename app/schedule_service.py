from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from typing import Any


def get_calendar_group_id(
    area_id: str,
    collection_schedule: dict[str, Any],
) -> str | None:
    """Return the calendar-group ID assigned to an area."""
    area_record = collection_schedule.get("area_index", {}).get(area_id)
    if not isinstance(area_record, dict):
        return None

    calendar_group_id = area_record.get("calendar_group_id")
    if not isinstance(calendar_group_id, str) or not calendar_group_id:
        return None

    return calendar_group_id


def get_calendar_group(
    area_id: str,
    collection_schedule: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the complete calendar-group record assigned to an area."""
    calendar_group_id = get_calendar_group_id(
        area_id=area_id,
        collection_schedule=collection_schedule,
    )
    if calendar_group_id is None:
        return None

    calendar_group = collection_schedule.get("calendar_groups", {}).get(
        calendar_group_id
    )
    if not isinstance(calendar_group, dict):
        return None

    return calendar_group


def get_area_record(
    area_id: str,
    collection_schedule: dict[str, Any],
) -> dict[str, Any] | None:
    """Return one bilingual area record from the schedule index."""
    area_record = collection_schedule.get("area_index", {}).get(area_id)
    if not isinstance(area_record, dict):
        return None

    return {
        "area_id": area_id,
        "name_en": area_record.get("name_en", ""),
        "name_ja": area_record.get("name_ja", ""),
        "calendar_group_id": area_record.get("calendar_group_id", ""),
    }


def get_japan_datetime() -> datetime:
    """Return the current timezone-aware date and time in Japan."""
    return datetime.now(ZoneInfo("Asia/Tokyo"))


def parse_put_out_by(collection_schedule: dict[str, Any]) -> time:
    """Parse the collection deadline, falling back safely to 08:30."""
    deadline_text = str(collection_schedule.get("put_out_by", "08:30")).strip()
    try:
        return time.fromisoformat(deadline_text)
    except ValueError:
        return time(8, 30)


def normalize_current_datetime(
    current_date: date | datetime | None,
) -> datetime:
    """Normalize an optional test value to a Japan-aware datetime.

    A supplied date is treated as the start of that date for backward-compatible
    deterministic tests. Normal application calls use the actual current Japan
    date and time.
    """
    japan_timezone = ZoneInfo("Asia/Tokyo")
    if current_date is None:
        return get_japan_datetime()
    if isinstance(current_date, datetime):
        if current_date.tzinfo is None:
            return current_date.replace(tzinfo=japan_timezone)
        return current_date.astimezone(japan_timezone)
    return datetime.combine(current_date, time.min, tzinfo=japan_timezone)


def get_next_collection_info(
    category_id: str,
    collection_schedule: dict[str, Any],
    current_date: date | datetime | None = None,
    area_id: str | None = None,
) -> dict[str, Any]:
    """Return the next usable collection opportunity and deadline metadata."""
    current_datetime = normalize_current_datetime(current_date)
    today = current_datetime.date()
    valid_from = date.fromisoformat(collection_schedule["valid_from"])
    valid_to = date.fromisoformat(collection_schedule["valid_to"])
    deadline = parse_put_out_by(collection_schedule)

    empty_result = {
        "next_date": None,
        "put_out_by": deadline.strftime("%H:%M"),
        "today_deadline_passed": False,
        "skipped_date": None,
    }
    if today < valid_from or today > valid_to:
        return empty_result

    if "calendar_groups" in collection_schedule:
        if not area_id:
            return empty_result
        calendar_group = get_calendar_group(
            area_id=area_id,
            collection_schedule=collection_schedule,
        )
        if calendar_group is None:
            return empty_result
        schedule = calendar_group.get("schedule", {})
    else:
        schedule = collection_schedule.get("schedule", {})

    category_schedule = schedule.get(category_id)
    if not isinstance(category_schedule, dict):
        return empty_result

    today_deadline_passed = current_datetime.time().replace(tzinfo=None) >= deadline
    skipped_date = None
    for collection_date_text in category_schedule.get("dates", []):
        collection_date = date.fromisoformat(collection_date_text)
        if collection_date < today:
            continue
        if collection_date == today and today_deadline_passed:
            skipped_date = collection_date_text
            continue
        return {
            "next_date": collection_date_text,
            "put_out_by": deadline.strftime("%H:%M"),
            "today_deadline_passed": skipped_date is not None,
            "skipped_date": skipped_date,
        }

    empty_result["today_deadline_passed"] = skipped_date is not None
    empty_result["skipped_date"] = skipped_date
    return empty_result


def get_next_collection_date(
    category_id: str,
    collection_schedule: dict[str, Any],
    current_date: date | datetime | None = None,
    area_id: str | None = None,
) -> str | None:
    """Return the next usable collection date.

    This compatibility wrapper preserves the existing public function while the
    richer deadline metadata is available through get_next_collection_info().
    """
    return get_next_collection_info(
        category_id=category_id,
        collection_schedule=collection_schedule,
        current_date=current_date,
        area_id=area_id,
    )["next_date"]
