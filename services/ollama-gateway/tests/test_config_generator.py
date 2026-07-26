# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("generator", ROOT / "tools" / "generate_litellm_config.py")
generator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(generator)


def test_generator_preserves_single_provider_prefixes():
    models, warnings = generator.build_model_list(
        {"local_ollama": {"expose_all": True}, "models": [{"name": "or", "provider": "openrouter", "model": "openrouter/auto"}]},
        {}, ["qwen:latest"]
    )
    assert not warnings
    text = generator.render(models)
    assert 'model: "ollama_chat/qwen:latest"' in text
    assert 'model: "openrouter/auto"' in text
    assert "openrouter/openrouter" not in text


def test_chatgpt_models_are_optional_logical_routes():
    models, _ = generator.build_model_list(
        {"local_ollama": {"expose_all": False}, "models": []},
        {"CHATGPT_MODELS": "coding=gpt-test-codex,general=gpt-test"}, []
    )
    text = generator.render(models)
    assert [m["name"] for m in models] == ["coding", "general"]
    assert 'model: "chatgpt/responses/gpt-test-codex"' in text
    assert 'model: "chatgpt/responses/gpt-test"' in text
    assert "mode: responses" in text
