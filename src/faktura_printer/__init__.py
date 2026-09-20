"""faktura-printer — render PDF invoices (fakturor) from JSON.

Quick start::

    from pathlib import Path
    from faktura_printer import Invoice, render_pdf

    invoice = Invoice.model_validate_json(Path("invoice.json").read_bytes())
    pdf_bytes = render_pdf(invoice, base_dir=Path("invoice.json").parent)
    Path("out.pdf").write_bytes(pdf_bytes)

``base_dir`` is where a relative ``seller.logo`` path is resolved (typically
the directory the JSON file lives in). See :func:`render_pdf` for the
``untrusted`` flag, needed when the JSON comes from an untrusted caller
(e.g. an HTTP request) rather than a local file you control.

Public API
----------
- :class:`Invoice` — pydantic model / JSON schema for the invoice input.
- :func:`render_pdf` / :func:`render_html` — render an :class:`Invoice`.
- :exc:`InvoiceError` — valid ``Invoice`` that still can't be rendered
  (unknown locale/theme, missing/unsupported logo or design file, ...).
- :func:`available_locales` / :func:`available_themes` / :func:`default_filename`
  — small helpers.

Visual design — a bundled theme (``invoice.design.theme``, see
:func:`available_themes`), or your own template/CSS (``invoice.design.template``,
``invoice.design.css``) — is set per :class:`Invoice`, so a single running
service can render different designs for different callers; see
:class:`Design`.

The optional CLI (``faktura-printer``) and HTTP API
(``faktura_printer.api``, needs the ``api`` extra) are thin wrappers around
this same API and are not required to use it as a library.
"""

from .models import Address, Buyer, Design, Invoice, Item, Seller, Totals
from .renderer import InvoiceError, available_locales, available_themes, default_filename, render_html, render_pdf

__version__ = "0.3.0"

__all__ = [
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
]
