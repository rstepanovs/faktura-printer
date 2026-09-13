"""Command line interface.

    faktura-printer invoice.json [-o out.pdf] [--html out.html]
    faktura-printer serve [--host H] [--port P] [--assets-dir DIR]
    faktura-printer schema
"""

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .models import Invoice
from .renderer import InvoiceError, default_filename, render_html, render_pdf


def _load_invoice(source: str) -> tuple[Invoice, Path]:
    if source == "-":
        return Invoice.model_validate_json(sys.stdin.buffer.read()), Path.cwd()
    path = Path(source)
    return Invoice.model_validate_json(path.read_bytes()), path.resolve().parent


def _print_validation_error(error: ValidationError) -> None:
    print(f"error: invalid invoice data ({error.error_count()} errors)", file=sys.stderr)
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"]) or "<root>"
        print(f"  {location}: {detail['msg']}", file=sys.stderr)


def _render(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="faktura-printer",
        description="Render an invoice JSON file to PDF.",
        epilog="Other commands: 'serve' runs the HTTP API, 'schema' prints the input JSON schema.",
    )
    parser.add_argument("input", help="invoice JSON file, or - for stdin")
    parser.add_argument("-o", "--output", type=Path, help="output PDF (default: faktura_<number>.pdf)")
    parser.add_argument("--html", type=Path, metavar="PATH", help="also write the intermediate HTML")
    args = parser.parse_args(argv)

    try:
        invoice, base_dir = _load_invoice(args.input)
        if args.html:
            args.html.write_text(render_html(invoice, base_dir=base_dir), encoding="utf-8")
        output = args.output or Path(default_filename(invoice))
        output.write_bytes(render_pdf(invoice, base_dir=base_dir))
    except ValidationError as error:
        _print_validation_error(error)
        return 1
    except (InvoiceError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(output)
    return 0


def _serve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="faktura-printer serve", description="Run the HTTP API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--assets-dir",
        type=Path,
        help="directory whose logo/template/css files requests may reference by name (FAKTURA_ASSETS_DIR)",
    )
    args = parser.parse_args(argv)
    if args.assets_dir:
        os.environ["FAKTURA_ASSETS_DIR"] = str(args.assets_dir.resolve())

    import uvicorn

    uvicorn.run("faktura_printer.api:app", host=args.host, port=args.port)
    return 0


def _schema(argv: list[str]) -> int:
    argparse.ArgumentParser(
        prog="faktura-printer schema", description="Print the JSON schema of the invoice input."
    ).parse_args(argv)
    print(json.dumps(Invoice.model_json_schema(), indent=2, ensure_ascii=False))
    return 0


COMMANDS = {"serve": _serve, "schema": _schema}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in COMMANDS:
        return COMMANDS[argv[0]](argv[1:])
    return _render(argv)


if __name__ == "__main__":
    sys.exit(main())
