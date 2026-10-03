"""Shared helpers for Paprika integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Tuple, Any, Optional, Dict

from homeassistant.util import dt as dt_util

MEAL_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_meal_datetime(value: str | None) -> Optional[datetime]:
    """Parse Paprika date string into localized datetime."""
    if not value:
        return None
    try:
        naive = datetime.strptime(value, MEAL_DATE_FORMAT)
    except ValueError:
        return None
    return naive.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)


def iter_future_meals(
    meals: Iterable[dict[str, Any]],
    *,
    reference: Optional[datetime] = None,
) -> Iterable[Tuple[datetime, dict[str, Any]]]:
    """Yield meals scheduled for now or the future."""
    now = reference or dt_util.now()
    for meal in meals:
        meal_dt = parse_meal_datetime(meal.get("date"))
        if meal_dt and meal_dt >= now:
            yield meal_dt, meal


def load_credentials_from_secrets(path: Path) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract Paprika credentials from Home Assistant secrets file."""
    email: Optional[str] = None
    password: Optional[str] = None
    receipt: Optional[str] = None

    if not path.exists():
        return email, password, receipt

    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key == "paprika_email":
                email = value
            elif key == "paprika_password":
                password = value
            elif key == "paprika_receipt":
                receipt = value
    except Exception:
        return None, None, None

    return email or None, password or None, receipt or None


def resolve_credentials(
    entry_data: dict[str, Any], secrets_path: Path
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve credentials, preferring the operator-managed secrets file.

    Config-entry values are retained as a fallback for installations that do
    not use ``secrets.yaml``. This also lets rotated credentials take effect
    without deleting and recreating the config entry.
    """
    secret_email, secret_password, secret_receipt = load_credentials_from_secrets(
        secrets_path
    )
    return (
        secret_email or entry_data.get("email"),
        secret_password or entry_data.get("password"),
        secret_receipt or entry_data.get("receipt"),
    )


def resolve_meal_time_windows(
    meal: dict[str, Any],
    meal_types: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[datetime, datetime] | None:
    """Return start/end datetimes for a meal using meal type metadata."""
    meal_dt = parse_meal_datetime(meal.get("date"))
    if not meal_dt:
        return None

    start = meal_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    type_uid = meal.get("type_uid")
    start_seconds = 0
    if meal_types and type_uid and type_uid in meal_types:
        mt = meal_types[type_uid]
        start_seconds = mt.get("export_time") or 0
        name = (mt.get("name") or "").lower()
        if name == "dinner":
            start_seconds = 17 * 3600 + 30 * 60  # 17:30
        elif name == "lunch":
            start_seconds = 12 * 3600 + 30 * 60  # 12:30
    start = start + timedelta(seconds=start_seconds)
    end = start + timedelta(hours=1)
    return start, end
