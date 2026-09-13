import datetime as dt
from decimal import Decimal

import pytest

from faktura_printer.formatting import format_date, format_decimal

SV = {"decimal_separator": ",", "thousands_separator": " "}
EN = {"decimal_separator": ".", "thousands_separator": ","}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("138000"), "138 000,00"),
        (Decimal("750"), "750,00"),
        (Decimal("1234567.891"), "1 234 567,89"),
        (Decimal("0.005"), "0,01"),
        (Decimal("-6000"), "-6 000,00"),
        (Decimal("-0.001"), "0,00"),
    ],
)
def test_money(value, expected):
    assert format_decimal(value, places=2, **SV) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("184"), "184"),
        (Decimal("184.0"), "184"),
        (Decimal("7.50"), "7,5"),
        (Decimal("1E+3"), "1 000"),
    ],
)
def test_number_drops_trailing_zeros(value, expected):
    assert format_decimal(value, places=None, **SV) == expected


def test_english_separators():
    assert format_decimal(Decimal("138000"), places=2, **EN) == "138,000.00"


def test_strings_and_none_pass_through():
    assert format_decimal("se avtal", places=2, **SV) == "se avtal"
    assert format_decimal(None, places=2, **SV) == ""


def test_date():
    assert format_date(dt.date(2026, 9, 14), "%Y-%m-%d") == "2026-09-14"
    assert format_date(dt.date(2026, 9, 14), "%d.%m.%Y") == "14.09.2026"
