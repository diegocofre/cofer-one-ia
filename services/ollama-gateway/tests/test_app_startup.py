from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[3]


def test_streaming_routes_disable_fastapi_response_model_generation():
    routes = {route.path: route for route in app.routes}
    for path in ("/api/chat", "/api/generate", "/v1/chat/completions", "/v1/responses", "/v1/messages", "/v1/messages/count_tokens"):
        assert routes[path].response_model is None


def test_gateway_version_and_protocol_surface():
    assert app.version == (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    routes = {route.path for route in app.routes}
    assert "/v1/models" in routes
    assert "/api/ps" in routes
