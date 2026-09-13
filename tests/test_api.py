import base64

import pytest
from conftest import LOGO
from fastapi.testclient import TestClient

from faktura_printer.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_assets_dir(monkeypatch):
    monkeypatch.delenv("FAKTURA_ASSETS_DIR", raising=False)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_create_invoice_with_data_uri_logo(data):
    data["seller"]["logo"] = "data:image/svg+xml;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    response = client.post("/invoices", json=data)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="faktura_1138.pdf"' in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_logo_by_name_from_assets_dir(data, monkeypatch):
    monkeypatch.setenv("FAKTURA_ASSETS_DIR", str(LOGO.parent))
    data["seller"]["logo"] = LOGO.name
    assert client.post("/invoices", json=data).status_code == 200


def test_logo_path_rejected_without_assets_dir(data):
    response = client.post("/invoices", json=data)
    assert response.status_code == 422
    assert "FAKTURA_ASSETS_DIR" in response.json()["detail"]


def test_bundled_theme_by_name(data):
    data["seller"]["logo"] = None
    data["design"] = {"theme": "modern"}
    response = client.post("/invoices", json=data)
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_custom_css_by_name_from_assets_dir(data, monkeypatch, tmp_path):
    data["seller"]["logo"] = None
    (tmp_path / "custom.css").write_text("body { background: #fffbea; }", encoding="utf-8")
    monkeypatch.setenv("FAKTURA_ASSETS_DIR", str(tmp_path))
    data["design"] = {"css": "custom.css"}
    assert client.post("/invoices", json=data).status_code == 200


def test_custom_css_path_rejected_without_assets_dir(data):
    data["design"] = {"css": "custom.css"}
    response = client.post("/invoices", json=data)
    assert response.status_code == 422
    assert "FAKTURA_ASSETS_DIR" in response.json()["detail"]


def test_validation_error(data):
    data.pop("items")
    response = client.post("/invoices", json=data)
    assert response.status_code == 422
    assert ["body", "items"] in [error["loc"] for error in response.json()["detail"]]
