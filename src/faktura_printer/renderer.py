"""Render an Invoice to HTML (Jinja2) and PDF (WeasyPrint)."""

import json
import re
from functools import cache
from importlib.resources import files
from pathlib import Path
from urllib import request
from urllib.parse import urlsplit

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from markupsafe import Markup
from weasyprint import HTML
from weasyprint.urls import URLFetcher

from .formatting import format_date, format_decimal
from .models import Invoice

LOGO_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg"}
TEMPLATE_SUFFIXES = {".j2"}
CSS_SUFFIXES = {".css"}
LOGO_DATA_URI = re.compile(r"data:image/(?:svg\+xml|png|jpeg);base64,[A-Za-z0-9+/=\s]+")

# Bundled themes live under themes/<name>.css; the HTML structure (themes/invoice.html.j2)
# is shared by all of them and only referenced by this fixed name.
_env = Environment(
    loader=PackageLoader("faktura_printer", package_path="themes"),
    autoescape=select_autoescape(["html", "j2"]),
    undefined=StrictUndefined,
)


class InvoiceError(ValueError):
    """A structurally valid :class:`~faktura_printer.Invoice` that still can't be
    rendered: unknown ``locale``/``labels``/``design.theme``, or a
    missing/unsupported/disallowed ``seller.logo``, ``design.template`` or
    ``design.css``."""


class RestrictedURLFetcher(URLFetcher):
    """WeasyPrint URL fetcher used in ``untrusted=True`` mode.

    Loads only ``data:`` URIs and files inside ``allowed_dir`` — this also
    covers resources an SVG logo or a custom stylesheet itself references
    (e.g. ``<image href="...">``, CSS ``url(...)``/``@import``) and blocks
    network access, so a hostile logo or stylesheet cannot exfiltrate data or
    read arbitrary server files. Not part of the public API; used internally
    by :func:`render_pdf`.
    """

    def __init__(self, allowed_dir: Path | None):
        super().__init__(allowed_protocols=("data", "file"))
        self._allowed_dir = allowed_dir

    def fetch(self, url, headers=None):
        if url.lower().startswith("file:"):
            path = Path(request.url2pathname(urlsplit(url).path)).resolve()
            if self._allowed_dir is None or not path.is_relative_to(self._allowed_dir):
                raise ValueError(f"access denied: {url}")
        return super().fetch(url, headers)


def available_locales() -> list[str]:
    """Return the locale codes ``Invoice.locale`` accepts, e.g. ``["en", "sv"]``.

    A locale is a JSON file under ``faktura_printer/locales/`` bundling
    printed labels plus number/date formatting; add a new one by dropping in
    a file with the same keys as ``locales/sv.json``.
    """
    directory = files("faktura_printer").joinpath("locales")
    return sorted(p.name.removesuffix(".json") for p in directory.iterdir() if p.name.endswith(".json"))


def available_themes() -> list[str]:
    """Return the bundled theme names ``Invoice.design.theme`` accepts, e.g. ``["classic", "modern"]``.

    A theme is a CSS file under ``faktura_printer/themes/`` styling the one
    bundled HTML structure (``themes/invoice.html.j2``); add one by dropping
    in a ``<name>.css`` file. For a different HTML structure altogether, use
    ``Invoice.design.template`` instead.
    """
    directory = files("faktura_printer").joinpath("themes")
    return sorted(p.name.removesuffix(".css") for p in directory.iterdir() if p.name.endswith(".css"))


@cache
def load_locale(code: str) -> dict:
    if code not in available_locales():
        raise InvoiceError(f"unknown locale {code!r}, available: {', '.join(available_locales())}")
    return json.loads(files("faktura_printer").joinpath("locales", f"{code}.json").read_text(encoding="utf-8"))


def default_filename(invoice: Invoice) -> str:
    """A filesystem-safe output file name for ``invoice``, e.g. ``"faktura_1138.pdf"``.

    Derived from ``invoice.invoice.number`` with everything but
    ``[A-Za-z0-9._-]`` replaced by ``_``. Used by the CLI when ``-o`` is
    omitted; handy for library callers that write the PDF to disk themselves.
    """
    number = re.sub(r"[^A-Za-z0-9._-]+", "_", invoice.invoice.number).strip("._") or "invoice"
    return f"faktura_{number}.pdf"


def _as_path(base_dir: Path | str | None) -> Path | None:
    return None if base_dir is None else Path(base_dir)


def _resolve_asset(
    path: str,
    base_dir: Path | None,
    untrusted: bool,
    *,
    allowed_suffixes: set[str],
    noun: str,
    no_base_dir_hint: str,
) -> Path:
    """Resolve a user-supplied asset path (``seller.logo``, ``design.template``,
    ``design.css``), relative to ``base_dir`` (default: cwd). In untrusted mode
    it must be a bare file name (no ``/`` or ``..``) that still resolves
    inside ``base_dir``, which must itself be given — see FAKTURA_ASSETS_DIR.
    """
    if untrusted:
        if base_dir is None:
            raise InvoiceError(f"{noun} file names are not accepted: {no_base_dir_hint}")
        if Path(path).name != path:
            raise InvoiceError(f"{noun} must be a bare file name inside the assets directory")
    resolved = ((base_dir or Path.cwd()) / path).resolve()
    if untrusted and not resolved.is_relative_to(base_dir.resolve()):
        raise InvoiceError(f"{noun} must be a bare file name inside the assets directory")
    if resolved.suffix.lower() not in allowed_suffixes:
        suffixes = ", ".join(sorted(allowed_suffixes))
        raise InvoiceError(f"unsupported {noun} format {resolved.suffix!r}, use {suffixes}")
    if not resolved.is_file():
        raise InvoiceError(f"{noun} file not found: {resolved}")
    return resolved


def _logo_src(logo: str | None, base_dir: Path | None, untrusted: bool) -> str | None:
    if not logo:
        return None
    if logo.startswith("data:"):
        if not LOGO_DATA_URI.fullmatch(logo):
            raise InvoiceError("logo data URI must be base64 data:image/svg+xml, image/png or image/jpeg")
        return logo
    path = _resolve_asset(
        logo,
        base_dir,
        untrusted,
        allowed_suffixes=LOGO_SUFFIXES,
        noun="logo",
        no_base_dir_hint="send a data URI or configure FAKTURA_ASSETS_DIR",
    )
    return path.as_uri()


def _read_design_asset(path: str, base_dir: Path | None, untrusted: bool, *, allowed_suffixes: set[str], noun: str) -> str:
    resolved = _resolve_asset(
        path,
        base_dir,
        untrusted,
        allowed_suffixes=allowed_suffixes,
        noun=noun,
        no_base_dir_hint="configure FAKTURA_ASSETS_DIR",
    )
    return resolved.read_text(encoding="utf-8")


def render_html(invoice: Invoice, *, base_dir: Path | str | None = None, untrusted: bool = False) -> str:
    """Render ``invoice`` to a standalone HTML document (the intermediate step
    of :func:`render_pdf`), mainly useful for debugging the layout in a browser.

    Args:
        invoice: A validated :class:`~faktura_printer.Invoice`.
        base_dir: Directory a relative ``seller.logo``, ``design.template`` or
            ``design.css`` path is resolved against (``str`` or ``Path``).
            Defaults to the current working directory.
        untrusted: Set when ``invoice`` came from an untrusted caller (e.g.
            an HTTP request body) rather than a local file you control. Then
            ``seller.logo`` must be either a ``data:`` URI or a bare file
            name, and ``design.template``/``design.css`` must be bare file
            names too — each resolving inside ``base_dir``, which must
            itself be given.

    Returns:
        The rendered HTML as a string.

    Raises:
        InvoiceError: Unknown ``invoice.locale``/``labels``/``design.theme``,
            or a missing/unsupported/disallowed ``seller.logo``,
            ``design.template`` or ``design.css``.
    """
    base_dir = _as_path(base_dir)
    locale = load_locale(invoice.locale)
    unknown = invoice.labels.keys() - locale["labels"].keys()
    if unknown:
        raise InvoiceError(f"unknown label(s): {', '.join(sorted(unknown))}")

    design = invoice.design
    if design.theme not in available_themes():
        raise InvoiceError(f"unknown theme {design.theme!r}, available: {', '.join(available_themes())}")

    if design.template:
        source = _read_design_asset(design.template, base_dir, untrusted, allowed_suffixes=TEMPLATE_SUFFIXES, noun="template")
        template = _env.from_string(source)
    else:
        template = _env.get_template("invoice.html.j2")

    if design.css:
        css = _read_design_asset(design.css, base_dir, untrusted, allowed_suffixes=CSS_SUFFIXES, noun="stylesheet")
    else:
        css = files("faktura_printer").joinpath("themes", f"{design.theme}.css").read_text(encoding="utf-8")

    separators = {key: locale[key] for key in ("decimal_separator", "thousands_separator")}
    return template.render(
        inv=invoice,
        lang=invoice.locale,
        L={**locale["labels"], **invoice.labels},
        css=Markup(css),  # raw CSS, not HTML-escaped
        logo_src=_logo_src(invoice.seller.logo, base_dir, untrusted),
        money=lambda value: format_decimal(value, places=2, **separators),
        number=lambda value: format_decimal(value, places=None, **separators),
        date=lambda value: format_date(value, locale["date_format"]),
    )


def render_pdf(invoice: Invoice, *, base_dir: Path | str | None = None, untrusted: bool = False) -> bytes:
    """Render ``invoice`` to a PDF document. This is the main entry point of the library.

    Args:
        invoice: A validated :class:`~faktura_printer.Invoice`.
        base_dir: Directory a relative ``seller.logo``, ``design.template`` or
            ``design.css`` path is resolved against (``str`` or ``Path``).
            Defaults to the current working directory.
        untrusted: Set when ``invoice`` came from an untrusted caller (e.g.
            an HTTP request body) rather than a local file you control. Then
            ``seller.logo`` must be either a ``data:`` URI or a bare file
            name, and ``design.template``/``design.css`` must be bare file
            names too — each resolving inside ``base_dir``, which must
            itself be given; WeasyPrint is further restricted to loading
            only ``data:`` URIs and files inside ``base_dir``, which also
            covers resources an SVG logo or custom stylesheet itself
            references.

    Returns:
        The rendered PDF as bytes (starts with ``b"%PDF"``).

    Raises:
        InvoiceError: Unknown ``invoice.locale``/``labels``/``design.theme``,
            or a missing/unsupported/disallowed ``seller.logo``,
            ``design.template`` or ``design.css``.

    Example:
        >>> from pathlib import Path
        >>> from faktura_printer import Invoice, render_pdf
        >>> json_path = Path("invoice.json")
        >>> invoice = Invoice.model_validate_json(json_path.read_bytes())
        >>> Path("out.pdf").write_bytes(render_pdf(invoice, base_dir=json_path.parent))
    """
    base_dir = _as_path(base_dir)
    html = render_html(invoice, base_dir=base_dir, untrusted=untrusted)
    if untrusted:
        fetcher = RestrictedURLFetcher(base_dir.resolve() if base_dir else None)
    else:
        fetcher = URLFetcher()
    return HTML(string=html, url_fetcher=fetcher).write_pdf()
