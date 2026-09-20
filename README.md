# faktura-printer

[![CI](https://github.com/rstepanovs/faktura-printer/actions/workflows/ci.yml/badge.svg)](https://github.com/rstepanovs/faktura-printer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/rstepanovs/faktura-printer)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)

Generates PDF invoices (Faktura) from JSON, following the Swedish faktura layout:
seller, buyer, logo, line items and totals all come from the input file.

Amounts are **never recalculated**: the app prints the values from the JSON,
only validating their structure and types.

Three ways to use it: as an **importable module** in another Python project, as a
**CLI**, or as an **HTTP API**. All three are thin wrappers around the same public
API (`faktura_printer.render_pdf`).

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -e .          # library only (Invoice, render_pdf, ...)
.venv/bin/pip install -e '.[api]'   # + HTTP API (faktura-printer serve)
.venv/bin/pip install -e '.[dev]'   # + tests (includes [api])
```

To use it as a dependency from another project:

```bash
pip install faktura-printer                         # once published to an index
pip install git+https://github.com/rstepanovs/faktura-printer   # or straight from GitHub
```

```toml
# another project's pyproject.toml
dependencies = ["faktura-printer @ git+https://github.com/rstepanovs/faktura-printer"]
```

WeasyPrint needs the Pango/HarfBuzz system libraries (usually already present on
Ubuntu; otherwise `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`).

## Using it as a library

```python
from pathlib import Path
from faktura_printer import Invoice, render_pdf

json_path = Path("invoice.json")
invoice = Invoice.model_validate_json(json_path.read_bytes())   # validate + parse
pdf_bytes = render_pdf(invoice, base_dir=json_path.parent)      # base_dir: where to look for the logo
Path("out.pdf").write_bytes(pdf_bytes)
```

Public API (`from faktura_printer import ...`, stable names, documented via
docstrings; the package ships `py.typed`):

| Name | Description |
|------|--------------|
| `Invoice`, `Seller`, `Buyer`, `Item`, `Totals`, `Address`, `Design` | pydantic models for the input data — see "JSON format" below; can be built programmatically, without JSON |
| `render_pdf(invoice, *, base_dir=None, untrusted=False)` | `Invoice` → PDF bytes |
| `render_html(invoice, *, base_dir=None, untrusted=False)` | `Invoice` → HTML string (for debugging the layout) |
| `InvoiceError` | subclass of `ValueError`: unknown locale/theme, or a missing/unsupported logo or design file |
| `available_locales()` | list of locale codes, e.g. `["en", "sv"]` |
| `available_themes()` | list of bundled themes, e.g. `["classic", "modern"]` |
| `default_filename(invoice)` | output file name from the invoice number, e.g. `"faktura_1138.pdf"` |

`base_dir` (`str` or `Path`) — where a relative `seller.logo`/`design.template`/
`design.css` is resolved from; defaults to the current directory. `untrusted=True`
is for when the `Invoice` was built from an external caller's data rather than a
local file you control (restrictions are covered in "HTTP API" below, which uses
this mode).

Full signatures and examples live in the docstrings (`help(faktura_printer.render_pdf)`,
or your IDE/type checker thanks to `py.typed`).

## CLI

```bash
# PDF next to the JSON, named after the invoice number: faktura_1138.pdf
.venv/bin/faktura-printer examples/invoice_1138.json

# custom output path + an intermediate HTML for debugging the layout
.venv/bin/faktura-printer examples/invoice_1138.json -o out.pdf --html out.html

# JSON from stdin
cat invoice.json | .venv/bin/faktura-printer - -o out.pdf

# JSON schema of the input
.venv/bin/faktura-printer schema > invoice.schema.json
```

Invalid data prints every offending field and exits with code `1`.

## HTTP API

Requires the `[api]` extra (`pip install -e '.[api]'` or `'.[dev]'`).

```bash
.venv/bin/faktura-printer serve --host 127.0.0.1 --port 8000 --assets-dir assets/logos
```

| Method | Path        | Description                                  |
|--------|-------------|-----------------------------------------------|
| POST   | `/invoices` | body: invoice JSON, response: `application/pdf` |
| GET    | `/health`   | `{"status": "ok"}`                             |
| GET    | `/docs`     | Swagger UI                                     |

Validation errors return `422` with the field details.

In the API, the logo (`seller.logo`) and design files (`design.template`,
`design.css`) may only be given as `data:image/...;base64,...` (logo) or as a
**bare file name** inside the `--assets-dir` directory (env var
`FAKTURA_ASSETS_DIR`). Bundled themes (`design.theme`) are unrestricted — they
ship with the package, not as files on the server's disk. No other server files
or network access are reachable from the renderer.

```bash
curl -X POST localhost:8000/invoices -H 'Content-Type: application/json' \
     -d "$(jq '.seller.logo = "beltandbraces.svg"' examples/invoice_1138.json)" -o faktura.pdf
```

## JSON format

Full example: `examples/invoice_1138.json`. Optional fields can be omitted —
the invoice will just show an empty cell.

| Field | Req. | Description |
|-------|:----:|-------------|
| `locale` | | `sv` (default) or `en` |
| `labels` | | overrides for individual labels, e.g. `{"title": "Kreditfaktura"}` |
| `design.theme` | | `classic` (default) or `modern` — see "Design and themes" below |
| `design.template`, `design.css` | | path to your own `.j2`/`.css`, fully replacing the bundled one |
| `seller.name` | ✓ | company name (printed instead of the logo when there is none) |
| `seller.logo` | | path relative to the JSON file, or a data URI; `.svg`, `.png`, `.jpg` |
| `seller.address` | ✓ | `care_of`, `street`, `postal_code`, `city`, `country` |
| `seller.phone`, `email`, `registered_office`, `bankgiro`, `iban`, `bic`, `org_number`, `vat_number` | | footer details |
| `seller.f_tax_approved` | | `true` → prints "Godkänd för F-skatt" |
| `buyer.name`, `buyer.address` | ✓ | the recipient |
| `buyer.org_number`, `buyer.vat_number` | | required on both parties for EU reverse charge |
| `invoice.number`, `date`, `due_date` | ✓ | dates as `YYYY-MM-DD` |
| `invoice.customer_number`, `payment_terms`, `late_interest`, `our_reference`, `your_reference`, `your_order_number`, `delivery_terms`, `delivery_method` | | |
| `invoice.currency` | | ISO 4217 code, e.g. `EUR`; when set, printed after the VAT/total labels instead of the locale's default (Swedish `kr`) |
| `items[]` | ✓ (≥1) | `article_number`, `description` ✓, `quantity`, `unit`, `unit_price`, `amount` ✓ |
| `totals` | ✓ | `net`, `excl_vat`, `vat_rate`, `vat_amount`, `total` |
| `notes` | | free text in a box below the table |

**Numbers.** A JSON number (`138000.00`) is formatted for the locale: `138 000,00`
for `sv`, `138,000.00` for `en`; quantity and the VAT rate are printed without
trailing zeros. A string (`"per contract"`) is printed verbatim.

## Logo

The recommended format is **SVG**: a vector, sharp at any print size or zoom.
`assets/logos/beltandbraces.svg` was produced from the vector `logo/Final file (PDF).pdf`:

```bash
pdftocairo -svg "logo/Final file (PDF).pdf" assets/logos/beltandbraces.svg
```

(the `viewBox` was then cropped to the artwork, dropping the white margins). PNG
is supported too; EPS and PDF are not accepted directly and need the same
conversion. The logo is fit into a 62×32 mm box.

## Design and themes

Each invoice can pick its own design — the theme is set right in the JSON
(`design.theme`), so one running service can render a different look for
different callers with no code changes.

**Bundled themes** (`design.theme`, defaults to `classic`) only change
colors/fonts/borders — the invoice's structure (what goes where) is the same
for all of them: `examples/invoice_modern_theme.json` uses
`"design": {"theme": "modern"}`. List: `faktura_printer.available_themes()`.
A new theme is just a `src/faktura_printer/themes/<name>.css` file — copy
`classic.css` or `modern.css` as a starting point.

**Your own template and/or stylesheet** (`design.template`, `design.css`) — the
`.j2`/`.css` path is resolved the same way as `seller.logo` (relative to the
JSON file; in the HTTP API, a bare file name from `--assets-dir` only). Each
file **fully replaces** the bundled one rather than extending it — copy
`src/faktura_printer/themes/invoice.html.j2` and/or a theme's CSS as your
starting point:

```json
"design": { "template": "my_invoice.html.j2", "css": "my_invoice.css" }
```

You can set only `css` (keeping the bundled layout) or only `template`
(inheriting the theme's CSS, provided your template itself inserts `{{ css }}`
into `<style>`).

## Configuration

- Labels and number/date formatting: `src/faktura_printer/locales/<code>.json`.
  A new language is a new file with the same set of keys.
- Bundled themes: `src/faktura_printer/themes/<name>.css`; the layout is shared
  by all themes in `src/faktura_printer/themes/invoice.html.j2` (see "Design and
  themes" above).

## Tests

```bash
.venv/bin/pytest
```
