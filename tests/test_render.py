import base64
import shutil
import subprocess

import pytest
from conftest import EXAMPLE, LOGO, ROOT
from weasyprint import HTML

from faktura_printer.models import Invoice
from faktura_printer.renderer import (
    InvoiceError,
    RestrictedURLFetcher,
    available_themes,
    default_filename,
    render_html,
    render_pdf,
)

NBSP = " "


def _invoice(data: dict) -> Invoice:
    return Invoice.model_validate(data)


def _page_count(invoice: Invoice, **kwargs) -> int:
    return len(HTML(string=render_html(invoice, **kwargs)).render().pages)


def _pdf_text(pdf: bytes, tmp_path) -> str:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext is not installed")
    path = tmp_path / "out.pdf"
    path.write_bytes(pdf)
    result = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True)
    return result.stdout.replace(NBSP, " ")


def _data_uri(content: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def test_example_pdf_contains_all_values(data, tmp_path):
    pdf = render_pdf(_invoice(data), base_dir=EXAMPLE.parent)
    assert pdf.startswith(b"%PDF")
    text = _pdf_text(pdf, tmp_path)
    for expected in [
        "Faktura", "1138", "1001", "2026-07-31",
        "Nordisk Konsult AB", "Kundvägen 10", "211 34", "Malmö",
        "Vår referens", "Alex Lindqvist", "45 dagar netto", "2026-09-14", "8.00 %",
        "Consultancy services Jul 2026", "Consultancy services Jun 2026 correction",
        "184 timmar", "8 timmar", "750,00", "138 000,00", "6 000,00",
        "144 000,00", "36 000,00", "180 000,00", "ATT BETALA",
        "Exempelvägen 8", "123 45", "Exempelstad", "070-000 00 00", "123-4567", "556677-8899",
        "info@beltandbraces.se", "SE556677889901", "Godkänd för F-skatt",
    ]:
        assert expected in text, expected


def test_example_fits_one_page(data):
    assert _page_count(_invoice(data), base_dir=EXAMPLE.parent) == 1


def test_long_invoice_repeats_table_header(data, tmp_path):
    data["items"] = [dict(data["items"][0], description=f"Item {n}") for n in range(60)]
    invoice = _invoice(data)
    assert _page_count(invoice, base_dir=EXAMPLE.parent) >= 2
    text = _pdf_text(render_pdf(invoice, base_dir=EXAMPLE.parent), tmp_path)
    assert text.count("Benämning") >= 2


def test_html_uses_locale_formatting_and_logo(data):
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert f"138{NBSP}000,00" in html
    assert LOGO.resolve().as_uri() in html


def test_english_locale(data):
    data["locale"] = "en"
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "<h1>Invoice</h1>" in html
    assert "138,000.00" in html


def test_label_override(data):
    data["labels"] = {"title": "Kreditfaktura"}
    assert "<h1>Kreditfaktura</h1>" in render_html(_invoice(data), base_dir=EXAMPLE.parent)


def test_without_logo_prints_seller_name(data):
    data["seller"]["logo"] = None
    html = render_html(_invoice(data))
    assert '<div class="seller-name">Belt &amp; Braces Software AB</div>' in html


def test_png_logo(data):
    data["seller"]["logo"] = "../logo/Final file (PNG).png"
    assert render_pdf(_invoice(data), base_dir=EXAMPLE.parent).startswith(b"%PDF")


def test_base_dir_accepts_a_plain_string(data):
    assert render_pdf(_invoice(data), base_dir=str(EXAMPLE.parent)).startswith(b"%PDF")


def test_user_text_is_escaped(data):
    data["notes"] = '<b>Betala</b> <img src="file:///etc/passwd">'
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "<img src=\"file" not in html
    assert "&lt;b&gt;Betala&lt;/b&gt;" in html


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.__setitem__("locale", "xx"), "unknown locale"),
        (lambda d: d.__setitem__("labels", {"titel": "x"}), "unknown label"),
        (lambda d: d["seller"].__setitem__("logo", "missing.svg"), "not found"),
        (lambda d: d["seller"].__setitem__("logo", "../logo/Final file (EPS).eps"), "unsupported logo format"),
        (lambda d: d["seller"].__setitem__("logo", "data:text/html;base64,PGI+"), "data URI"),
    ],
    ids=["locale", "label", "missing-logo", "eps-logo", "non-image-data-uri"],
)
def test_render_errors(data, change, message):
    change(data)
    with pytest.raises(InvoiceError, match=message):
        render_html(_invoice(data), base_dir=EXAMPLE.parent)


def test_currency_empty_keeps_todays_output(data):
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "Moms kr" in html
    assert "ATT BETALA" in html


def test_currency_set_replaces_the_default_unit(data):
    data["invoice"]["currency"] = "EUR"
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "Moms EUR" in html
    assert "ATT BETALA EUR" in html
    assert "Moms kr" not in html


def test_buyer_identifiers_are_printed_when_set(data):
    data["buyer"]["org_number"] = "12345678"
    data["buyer"]["vat_number"] = "DE123456789"
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "12345678" in html
    assert "DE123456789" in html


def test_buyer_identifiers_are_omitted_when_blank(data):
    # The example seller already carries org_number/vat_number (printed in the footer);
    # with the buyer's left blank, each label appears exactly once.
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert html.count("Organisationsnr") == 1
    assert html.count("Momsreg.nr") == 1


def test_default_filename(data):
    data["invoice"]["number"] = "2026/1138"
    assert default_filename(_invoice(data)) == "faktura_2026_1138.pdf"


# Design: bundled themes and custom template/css


def test_available_themes_include_the_bundled_ones():
    assert {"classic", "modern"} <= set(available_themes())


def test_default_theme_is_classic(data):
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "#444" in html  # classic.css's dotted border color
    assert "#0f6f63" not in html  # modern.css's accent color


def test_modern_theme_changes_the_stylesheet(data):
    data["design"] = {"theme": "modern"}
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "#0f6f63" in html
    assert render_pdf(_invoice(data), base_dir=EXAMPLE.parent).startswith(b"%PDF")


def test_modern_theme_example_fits_one_page(data):
    data["design"] = {"theme": "modern"}
    assert _page_count(_invoice(data), base_dir=EXAMPLE.parent) == 1


def test_unknown_theme_is_rejected(data):
    data["design"] = {"theme": "brutalist"}
    with pytest.raises(InvoiceError, match="unknown theme"):
        render_html(_invoice(data), base_dir=EXAMPLE.parent)


def test_custom_css_replaces_the_theme_stylesheet(data, tmp_path):
    css_path = tmp_path / "custom.css"
    css_path.write_text("body { background: #fffbea; } /* custom */", encoding="utf-8")
    data["design"] = {"css": str(css_path)}
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "/* custom */" in html
    assert "@page" not in html  # the theme's own CSS is gone, not merged in


def test_custom_css_is_not_html_escaped(data, tmp_path):
    css_path = tmp_path / "custom.css"
    css_path.write_text("td > .num { color: red; }", encoding="utf-8")
    data["design"] = {"css": str(css_path)}
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "td > .num" in html
    assert "&gt;" not in html


def test_custom_template_replaces_the_bundled_html(data, tmp_path):
    template_path = tmp_path / "custom.j2"
    template_path.write_text("<html><body>Hello {{ inv.buyer.name }}</body></html>", encoding="utf-8")
    data["design"] = {"template": str(template_path)}
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert html == "<html><body>Hello Nordisk Konsult AB</body></html>"


def test_custom_template_user_data_is_still_escaped(data, tmp_path):
    template_path = tmp_path / "custom.j2"
    template_path.write_text("<body>{{ inv.notes }}</body>", encoding="utf-8")
    data["design"] = {"template": str(template_path)}
    data["notes"] = "<b>hi</b>"
    html = render_html(_invoice(data), base_dir=EXAMPLE.parent)
    assert "&lt;b&gt;hi&lt;/b&gt;" in html


@pytest.mark.parametrize(
    ("field", "suffix", "message"),
    [
        ("template", ".txt", "unsupported template format"),
        ("css", ".txt", "unsupported stylesheet format"),
    ],
)
def test_design_file_format_is_validated(data, tmp_path, field, suffix, message):
    path = tmp_path / f"custom{suffix}"
    path.write_text("x", encoding="utf-8")
    data["design"] = {field: str(path)}
    with pytest.raises(InvoiceError, match=message):
        render_html(_invoice(data), base_dir=EXAMPLE.parent)


def test_design_file_not_found(data):
    data["design"] = {"css": "missing.css"}
    with pytest.raises(InvoiceError, match="not found"):
        render_html(_invoice(data), base_dir=EXAMPLE.parent)


# Untrusted mode (HTTP API)


def test_untrusted_accepts_data_uri(data):
    data["seller"]["logo"] = _data_uri(LOGO.read_bytes(), "image/svg+xml")
    assert render_pdf(_invoice(data), untrusted=True).startswith(b"%PDF")


def test_untrusted_accepts_file_name_in_logo_dir(data):
    data["seller"]["logo"] = LOGO.name
    html = render_html(_invoice(data), base_dir=LOGO.parent, untrusted=True)
    assert LOGO.resolve().as_uri() in html


def test_untrusted_rejects_file_names_without_assets_dir(data):
    data["seller"]["logo"] = LOGO.name
    with pytest.raises(InvoiceError, match="FAKTURA_ASSETS_DIR"):
        render_pdf(_invoice(data), untrusted=True)


def test_untrusted_accepts_theme_by_name_and_css_by_name_from_assets_dir(data, tmp_path):
    data["seller"]["logo"] = None
    css_path = tmp_path / "custom.css"
    css_path.write_text("body { background: #fffbea; }", encoding="utf-8")
    data["design"] = {"theme": "modern", "css": css_path.name}
    html = render_html(_invoice(data), base_dir=tmp_path, untrusted=True)
    assert "#fffbea" in html


def test_untrusted_rejects_design_paths_outside_assets_dir(data, tmp_path):
    outside = tmp_path.parent / "outside.css"
    outside.write_text("body {}", encoding="utf-8")
    data["design"] = {"css": str(outside)}
    with pytest.raises(InvoiceError):
        render_pdf(_invoice(data), base_dir=tmp_path, untrusted=True)


@pytest.mark.parametrize("logo", ["../../pyproject.toml", "../logos/beltandbraces.svg", str(LOGO)])
def test_untrusted_rejects_paths(data, logo):
    data["seller"]["logo"] = logo
    with pytest.raises(InvoiceError):
        render_pdf(_invoice(data), base_dir=LOGO.parent, untrusted=True)


def test_restricted_fetcher_blocks_other_files_and_network():
    fetcher = RestrictedURLFetcher(LOGO.parent.resolve())
    fetcher.fetch(LOGO.resolve().as_uri()).close()
    with pytest.raises(ValueError):
        fetcher.fetch((ROOT / "pyproject.toml").as_uri())
    with pytest.raises(ValueError):
        fetcher.fetch("https://example.com/logo.png")


def test_untrusted_svg_resources_go_through_restricted_fetcher(data, monkeypatch, tmp_path):
    secret = tmp_path / "secret.png"
    secret.write_bytes((ROOT / "logo" / "Final file (PNG).png").read_bytes())
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        f'<image href="{secret.as_uri()}" width="10" height="10"/></svg>'
    )
    data["seller"]["logo"] = _data_uri(svg.encode(), "image/svg+xml")

    requested = []
    original_fetch = RestrictedURLFetcher.fetch

    def spy(self, url, headers=None):
        requested.append(url)
        return original_fetch(self, url, headers)

    monkeypatch.setattr(RestrictedURLFetcher, "fetch", spy)
    render_pdf(_invoice(data), untrusted=True)
    assert secret.as_uri() in requested
