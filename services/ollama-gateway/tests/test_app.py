# SPDX-License-Identifier: Apache-2.0

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


def test_fastapi_app_imports_and_root_responds():
    """Regression: route registration must not fail on Response union annotations."""
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "cofer-one-ia"
    assert payload["service"] == "universal-gateway"


def test_response_routes_disable_fastapi_response_model_inference():
    """Streaming/non-streaming Response unions are not valid Pydantic models."""
    routes = {
        route.path: route
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    for path in ("/api/chat", "/api/generate"):
        assert path in routes
        assert routes[path].response_model is None
