from app.main import app


def test_streaming_routes_disable_fastapi_response_model_generation():
    routes = {route.path: route for route in app.routes}
    for path in ("/api/chat", "/api/generate", "/v1/chat/completions", "/v1/responses", "/v1/messages"):
        assert routes[path].response_model is None


def test_gateway_version_and_protocol_surface():
    assert app.version == "0.2.0"
    routes = {route.path for route in app.routes}
    assert "/v1/models" in routes
    assert "/api/ps" in routes
