import json

from conftest import EXAMPLE

from faktura_printer.cli import main


def test_render_pdf_and_html(tmp_path, capsys):
    pdf = tmp_path / "out.pdf"
    html = tmp_path / "out.html"
    assert main([str(EXAMPLE), "-o", str(pdf), "--html", str(html)]) == 0
    assert pdf.read_bytes().startswith(b"%PDF")
    assert "ATT BETALA" in html.read_text(encoding="utf-8")
    assert capsys.readouterr().out.strip() == str(pdf)


def test_default_output_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main([str(EXAMPLE)]) == 0
    assert (tmp_path / "faktura_1138.pdf").read_bytes().startswith(b"%PDF")


def test_invalid_input_reports_every_error(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text('{"locale": "sv"}', encoding="utf-8")
    assert main([str(bad), "-o", str(tmp_path / "x.pdf")]) == 1
    err = capsys.readouterr().err
    for field in ("seller", "buyer", "invoice", "items", "totals"):
        assert field in err
    assert not (tmp_path / "x.pdf").exists()


def test_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.json")]) == 1
    assert "error:" in capsys.readouterr().err


def test_schema(capsys):
    assert main(["schema"]) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "Invoice"
