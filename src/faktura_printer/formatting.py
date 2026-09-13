"""Locale-aware formatting of numbers and dates for printing."""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal


def _group_digits(digits: str, separator: str) -> str:
    head = len(digits) % 3 or 3
    groups = [digits[:head]] + [digits[i : i + 3] for i in range(head, len(digits), 3)]
    return separator.join(groups)


def format_decimal(
    value: Decimal | str | None,
    *,
    places: int | None,
    decimal_separator: str,
    thousands_separator: str,
) -> str:
    """Format a Decimal; strings pass through verbatim, None becomes "".

    With ``places=None`` trailing zeros are dropped (184.0 -> "184").
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if places is None:
        value = value.normalize()
    else:
        value = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    whole, _, fraction = format(abs(value), "f").partition(".")
    text = _group_digits(whole, thousands_separator)
    if fraction:
        text += decimal_separator + fraction
    return f"-{text}" if value < 0 else text


def format_date(value: dt.date | str, date_format: str) -> str:
    """Format a date with ``date_format`` (a :meth:`~datetime.date.strftime` pattern);
    a string passes through verbatim."""
    if isinstance(value, str):
        return value
    return value.strftime(date_format)
