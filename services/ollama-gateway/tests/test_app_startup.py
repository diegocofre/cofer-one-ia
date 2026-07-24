from app.main import app


def test_streaming_routes_disable_fastapi_response_model_generation():
    routes = {route.path: route for route in app.routes}

    assert routes["/api/chat"].response_model is None
    assert routes["/api/generate"].response_model is None
