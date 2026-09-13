"""Exercises faktura_printer purely as an imported library: only the names
documented in the package docstring / README, never internal submodules."""

from decimal import Decimal

import faktura_printer
import pytest
from conftest import EXAMPLE

from faktura_printer import Buyer, Design, Invoice, InvoiceError, Seller, render_pdf


def test_all_matches_documented_surface():
    assert set(faktura_printer.__all__) == {
        "__version__",
        "Invoice",
        "Seller",
        "Buyer",
        "Item",
        "Totals",
        "Address",
        "Design",
        "InvoiceError",
        "render_html",
        "render_pdf",
        "available_locales",
        "available_themes",
        "default_filename",
    }
    assert all(hasattr(faktura_printer, name) for name in faktura_printer.__all__)


def test_version_is_a_string():
    assert isinstance(faktura_printer.__version__, str) and faktura_printer.__version__


def test_available_locales_include_the_bundled_ones():
    assert {"sv", "en"} <= set(faktura_printer.available_locales())


def test_available_themes_include_the_bundled_ones():
    assert {"classic", "modern"} <= set(faktura_printer.available_themes())


def test_end_to_end_round_trip_from_json_file():
    invoice = Invoice.model_validate_json(EXAMPLE.read_bytes())
    pdf = render_pdf(invoice, base_dir=EXAMPLE.parent)
    assert pdf.startswith(b"%PDF")
    assert faktura_printer.default_filename(invoice) == "faktura_1138.pdf"


def test_invoice_can_be_built_directly_without_json(data):
    invoice = Invoice(
        seller=Seller(name="Acme AB", address=data["seller"]["address"]),
        buyer=Buyer(name="Client AB", address=data["buyer"]["address"]),
        design=Design(theme="modern"),
        invoice=data["invoice"],
        items=data["items"],
        totals=data["totals"],
    )
    assert render_pdf(invoice).startswith(b"%PDF")
    assert invoice.items[0].amount == Decimal("138000.00")


def test_invoice_error_is_a_value_error_raised_via_public_api(data):
    data["locale"] = "xx"
    with pytest.raises(InvoiceError):
        render_pdf(Invoice.model_validate(data), base_dir=EXAMPLE.parent)
    assert issubclass(InvoiceError, ValueError)
