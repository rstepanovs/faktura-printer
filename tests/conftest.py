import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
EXAMPLE = ROOT / "examples" / "invoice_1138.json"
LOGO = ROOT / "assets" / "logos" / "beltandbraces.svg"


@pytest.fixture
def data() -> dict:
    """The example invoice as a mutable dict."""
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))
