"""HTTP API: POST an invoice JSON, receive the PDF.

Requests are untrusted: a logo must be a data URI, or the bare file name of
a file inside FAKTURA_ASSETS_DIR; a custom design.template/design.css must be
a bare file name inside that same directory. No other server files are
readable.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from .models import Invoice
from .renderer import InvoiceError, default_filename, render_pdf

app = FastAPI(title="faktura-printer", version="0.3.0")


def _assets_dir() -> Path | None:
    value = os.environ.get("FAKTURA_ASSETS_DIR")
    return Path(value).resolve() if value else None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/invoices",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The rendered invoice"}},
)
def create_invoice(invoice: Invoice) -> Response:
    try:
        pdf = render_pdf(invoice, base_dir=_assets_dir(), untrusted=True)
    except InvoiceError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{default_filename(invoice)}"'},
    )
