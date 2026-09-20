from decimal import Decimal

import pytest
from conftest import EXAMPLE
from pydantic import ValidationError

from faktura_printer.models import Invoice


def test_example_is_valid():
    invoice = Invoice.model_validate_json(EXAMPLE.read_bytes())
    assert invoice.invoice.number == "1138"
    assert invoice.items[0].quantity == Decimal("184")
    assert invoice.totals.total == Decimal("180000.00")
    assert invoice.seller.f_tax_approved is True


def test_json_number_is_decimal_and_string_is_verbatim(data):
    data["items"][0]["amount"] = "138 000,00 kr"
    invoice = Invoice.model_validate(data)
    assert invoice.items[0].amount == "138 000,00 kr"
    assert isinstance(invoice.items[1].amount, Decimal)


def test_numeric_invoice_number_is_coerced_to_string(data):
    data["invoice"]["number"] = 1138
    assert Invoice.model_validate(data).invoice.number == "1138"


def test_currency_and_buyer_identifiers_default_to_empty():
    invoice = Invoice.model_validate_json(EXAMPLE.read_bytes())
    assert invoice.invoice.currency == ""
    assert invoice.buyer.org_number == ""
    assert invoice.buyer.vat_number == ""


def test_currency_and_buyer_identifiers_round_trip(data):
    data["invoice"]["currency"] = "EUR"
    data["buyer"]["org_number"] = "12345678"
    data["buyer"]["vat_number"] = "DE123456789"
    invoice = Invoice.model_validate(data)
    assert invoice.invoice.currency == "EUR"
    assert invoice.buyer.org_number == "12345678"
    assert invoice.buyer.vat_number == "DE123456789"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("items"),
        lambda d: d.__setitem__("items", []),
        lambda d: d.pop("totals"),
        lambda d: d["buyer"].pop("name"),
        lambda d: d["invoice"].__setitem__("due_date", "14/09/2026"),
        lambda d: d["seller"].__setitem__("unknown_field", "x"),
        lambda d: d["totals"].__setitem__("total", None),
    ],
    ids=["no-items", "empty-items", "no-totals", "no-buyer-name", "bad-date", "extra-field", "null-total"],
)
def test_invalid_input_is_rejected(data, mutate):
    mutate(data)
    with pytest.raises(ValidationError):
        Invoice.model_validate(data)
