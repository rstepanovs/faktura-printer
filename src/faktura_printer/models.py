"""Pydantic models describing the invoice JSON input.

Amounts are taken ready-made from the input and are never recalculated.
A JSON number is parsed as Decimal and formatted for the locale; a JSON
string is printed verbatim.
"""

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

Amount = Decimal | str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Address(StrictModel):
    """A postal address. Every field is optional; blanks print as empty cells."""

    care_of: str = ""
    street: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = ""


class Seller(StrictModel):
    """The issuer of the invoice, printed in the header and footer."""

    name: str = Field(min_length=1, description="Printed instead of the logo when there is none")
    address: Address
    logo: str | None = Field(
        default=None,
        description="Path relative to the JSON file, or a data:image/...;base64 URI. "
        "Supported formats: .svg, .png, .jpg/.jpeg.",
    )
    phone: str = ""
    email: str = ""
    registered_office: str = ""
    bankgiro: str = ""
    iban: str = ""
    bic: str = ""
    org_number: str = ""
    vat_number: str = ""
    f_tax_approved: bool = Field(default=False, description="Prints the 'approved for F-tax' notice")


class Buyer(StrictModel):
    """The recipient of the invoice."""

    name: str = Field(min_length=1)
    address: Address
    org_number: str = ""
    vat_number: str = Field(default="", description="Required on both parties for EU reverse charge")


class InvoiceInfo(StrictModel):
    """Invoice header fields: numbers, dates and payment terms."""

    # Invoice/customer numbers are often written as JSON numbers.
    model_config = ConfigDict(coerce_numbers_to_str=True)

    number: str = Field(min_length=1)
    customer_number: str = ""
    currency: str = Field(
        default="", description="ISO 4217 code, e.g. 'EUR'. When set, printed after the VAT/total labels."
    )
    date: dt.date
    due_date: dt.date
    payment_terms: str = ""
    late_interest: str = ""
    our_reference: str = ""
    your_reference: str = ""
    your_order_number: str = ""
    delivery_terms: str = ""
    delivery_method: str = ""


class Item(StrictModel):
    """One line of the invoice table.

    ``quantity``, ``unit_price`` and ``amount`` are printed as given, never
    computed from one another — see :class:`Totals`.
    """

    article_number: str = ""
    description: str = Field(min_length=1)
    quantity: Amount | None = None
    unit: str = ""
    unit_price: Amount | None = None
    amount: Amount


class Totals(StrictModel):
    """Invoice totals, taken ready-made from the input and printed as-is.

    A numeric field is formatted for the locale (e.g. ``138000`` ->
    ``"138 000,00"``); a string field is printed verbatim.
    """

    net: Amount
    excl_vat: Amount
    vat_rate: Amount
    vat_amount: Amount
    total: Amount


class Design(StrictModel):
    """Visual design of the invoice: a bundled theme, or files that replace it.

    ``template``/``css`` are resolved the same way as ``seller.logo`` (path
    relative to the JSON file, or a bare file name inside a server-approved
    directory when the invoice comes from an untrusted caller — see
    :func:`~faktura_printer.render_pdf`). Each **replaces the whole** bundled
    file, not just part of it; base a custom stylesheet on a bundled theme's
    CSS (see :func:`~faktura_printer.available_themes`) if you only want to
    tweak colors or spacing rather than rebuild it from scratch.
    """

    theme: str = Field(default="classic", description="A theme name from faktura_printer.available_themes()")
    template: str | None = Field(
        default=None,
        description="Path to a custom Jinja2 template (.j2) replacing the bundled invoice.html.j2",
    )
    css: str | None = Field(
        default=None,
        description="Path to a custom stylesheet (.css) replacing the theme's CSS",
    )


class Invoice(StrictModel):
    """The complete invoice input: everything :func:`~faktura_printer.render_pdf` needs.

    Construct it from JSON with :meth:`~pydantic.BaseModel.model_validate_json`
    (bytes/str) or :meth:`~pydantic.BaseModel.model_validate` (a dict), or
    build it directly, e.g. ``Invoice(seller=..., buyer=..., invoice=..., items=[...], totals=...)``.
    Unknown fields anywhere in the input are rejected.
    """

    locale: str = Field(default="sv", description="A locale name from faktura_printer.available_locales()")
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Overrides for individual locale labels, e.g. {'title': 'Kreditfaktura'}",
    )
    design: Design = Field(default_factory=Design, description="Visual design; defaults to the 'classic' theme")
    seller: Seller
    buyer: Buyer
    invoice: InvoiceInfo
    items: list[Item] = Field(min_length=1)
    totals: Totals
    notes: str = Field(default="", description="Free text printed in a box below the items table")
