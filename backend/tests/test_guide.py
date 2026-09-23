"""K anti-rot: every GodLaws field and every REST route is mentioned in the guide."""

from fastapi.testclient import TestClient

from app.main import app
from app.protocol import GodLaws


def test_guide_serves_html_and_mentions_all_laws_and_routes():
    client = TestClient(app)
    r = client.get("/guide")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text

    # nav and sections
    assert "Flatland Guide" in body
    assert 'id="god-laws"' in body or "God laws" in body
    assert 'id="api-reference"' in body

    # every GodLaws field appears (law table + how-it-works)
    for name in GodLaws.model_fields.keys():
        assert name in body, f"GodLaws field {name!r} missing from guide"

    # every REST route appears (API table)
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path or path.startswith("/guide") or path.startswith("/openapi") or path.startswith("/docs") or path.startswith("/redoc"):
            continue
        # only check REST-ish routes
        if path.startswith("/api/") or path in ("/healthz", "/ws"):
            assert path in body, f"route {path!r} missing from guide"

    # json variant also mentions laws
    r2 = client.get("/guide?format=json")
    assert r2.status_code == 200
    j = r2.json()
    assert set(j["laws"]) == set(GodLaws.model_fields.keys())
    assert "/api/state" in j["routes"]


def test_guide_contains_expected_sections():
    client = TestClient(app)
    body = client.get("/guide").text
    for phrase in [
        "How the world works",
        "Codebase map",
        "Data model",
        "Configuration",
        "simulation.py:335",  # file:line anchor
        "protocol.py:98",
        "TODO.md",
    ]:
        assert phrase in body
