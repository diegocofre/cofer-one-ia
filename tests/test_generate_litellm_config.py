from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "generate_litellm_config.py"
spec = importlib.util.spec_from_file_location("generate_litellm_config", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_cofer_u_pass_models_are_restricted_openai_backends():
    policy = {"local_ollama": {"expose_all": False}, "models": []}
    env = {
        "COFER_U_PASS_MODELS": "cupass-chatgpt=chatgpt-main",
        "COFER_U_PASS_BRIDGE_KEY": "secret",
    }
    models, warnings = module.build_model_list(policy, env, [])
    assert warnings == []
    assert models[0]["provider"] == "cofer_u_pass"
    rendered = module.render(models)
    assert 'model_name: "cupass-chatgpt"' in rendered
    assert 'model: "openai/chatgpt-main"' in rendered
    assert "api_base: os.environ/COFER_U_PASS_BRIDGE_URL" in rendered
    assert "mode: responses" in rendered
    caps = module.model_capabilities(models[0])
    assert caps["tools"] is False
    assert caps["bundle_output"] is True


def test_cofer_u_pass_model_is_skipped_without_bridge_key():
    policy = {"local_ollama": {"expose_all": False}, "models": []}
    models, warnings = module.build_model_list(policy, {"COFER_U_PASS_MODELS": "cupass-chatgpt=chatgpt-main"}, [])
    assert models == []
    assert "COFER_U_PASS_BRIDGE_KEY" in warnings[0]
