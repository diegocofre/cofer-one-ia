# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("generator", ROOT / "tools" / "generate_litellm_config.py")
generator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(generator)


def test_generator_preserves_single_provider_prefixes():
    models, warnings = generator.build_model_list(
        {
            "local_ollama": {"expose_all": True},
            "models": [
                {
                    "name": "or",
                    "provider": "openrouter",
                    "model": "openrouter/auto",
                    "active": True,
                }
            ],
        },
        {},
        ["qwen:latest"],
    )
    assert not warnings
    text = generator.render(models)
    assert 'model: "openai/qwen:latest"' in text
    assert 'api_base: os.environ/OLLAMA_OPENAI_BASE_URL' in text
    assert 'api_key: "ollama"' in text
    assert 'model_name: "cofer-anthropic--qwen:latest"' in text
    assert 'model: "ollama_chat/qwen:latest"' in text
    assert 'api_base: os.environ/OLLAMA_BACKEND_URL' in text
    assert 'model_name: "cofer-openrouter--or"' in text
    assert 'model: "openai/auto"' in text
    assert 'api_base: os.environ/OPENROUTER_API_BASE' in text
    assert 'model_name: "cofer-anthropic--or"' in text
    assert 'model: "openrouter/auto"' in text
    assert "openrouter/openrouter" not in text


def test_active_false_hides_static_model():
    policy = {
        "local_ollama": {"expose_all": False},
        "models": [
            {"name": "on", "provider": "ollama", "model": "qwen:on", "active": True},
            {"name": "off", "provider": "ollama", "model": "qwen:off", "active": False},
        ],
    }
    models, warnings = generator.build_model_list(policy, {}, [])
    assert not warnings
    assert [model["name"] for model in models] == ["on"]


def test_missing_active_defaults_to_inactive():
    policy = {
        "local_ollama": {"expose_all": False},
        "models": [{"name": "implicit", "provider": "ollama", "model": "qwen:implicit"}],
    }
    models, warnings = generator.build_model_list(policy, {}, [])
    assert not warnings
    assert models == []


def test_legacy_enabled_true_remains_supported():
    policy = {
        "local_ollama": {"expose_all": False},
        "models": [{"name": "legacy", "provider": "ollama", "model": "qwen:legacy", "enabled": True}],
    }
    models, warnings = generator.build_model_list(policy, {}, [])
    assert not warnings
    assert [model["name"] for model in models] == ["legacy"]


def test_fixed_remote_catalog_and_physical_routes():
    policy = json.loads((ROOT / "config" / "models.json").read_text(encoding="utf-8"))
    expected = {
        "minimax-m3:cloud": ("ollama_cloud", "minimax-m3:cloud"),
        "nemotron-3-super:cloud": ("ollama_cloud", "nemotron-3-super:cloud"),
        "google/gemma-4-31b-it:free": ("openrouter", "google/gemma-4-31b-it:free"),
        "nvidia/nemotron-3-super-120b-a12b:free": ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free"),
        "nvidia/nemotron-3-ultra:free": ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
        "inclusionai/ling-3.0-flash:free": ("openrouter", "inclusionai/ling-3.0-flash:free"),
        "poolside/laguna-m.1:free": ("openrouter", "poolside/laguna-m.1:free"),
        "openai/gpt-5.6-sol": ("chatgpt", "gpt-5.6-sol"),
        "openai/gpt-5.6-terra": ("chatgpt", "gpt-5.6-terra"),
        "openai/gpt-5.6-luna": ("chatgpt", "gpt-5.6-luna"),
        "openai/gpt-5.4-mini": ("chatgpt", "gpt-5.4-mini"),
    }
    configured = {item["name"]: (item["provider"], item["model"]) for item in policy["models"]}
    assert configured == expected
    assert all(item["active"] is True for item in policy["models"])

    ollama_cloud = [item for item in policy["models"] if item["provider"] == "ollama_cloud"]
    openrouter = [item for item in policy["models"] if item["provider"] == "openrouter"]
    chatgpt = [item for item in policy["models"] if item["provider"] == "chatgpt"]
    assert len(ollama_cloud) == 2
    assert all("requires_env" not in item for item in ollama_cloud)
    assert all(item.get("requires_env") == ["OPENROUTER_API_KEY"] for item in openrouter)
    assert all("requires_env" not in item for item in chatgpt)

    models, warnings = generator.build_model_list(policy, {"OPENROUTER_API_KEY": "test-key"}, [])
    assert not warnings
    assert [model["name"] for model in models] == list(expected)

    rendered = generator.render(models)
    for logical, (provider, physical) in expected.items():
        if provider == "ollama_cloud":
            target = f"openai/{physical}"
            assert f'model_name: "{logical}"' in rendered
            assert 'api_base: os.environ/OLLAMA_OPENAI_BASE_URL' in rendered
        elif provider == "openrouter":
            normalized = physical.removeprefix("openrouter/")
            target = f"openai/{normalized}"
            internal = f"cofer-openrouter--{logical}"
            assert f'model_name: "{internal}"' in rendered
            assert f'model_name: "{logical}"' not in rendered
            assert 'api_base: os.environ/OPENROUTER_API_BASE' in rendered
        else:
            target = f"chatgpt/{physical}"
            internal = f"cofer-chatgpt--{logical.removeprefix('openai/')}"
            assert f'model_name: "{internal}"' in rendered
            assert f'model_name: "{logical}"' not in rendered
        assert f'model: "{target}"' in rendered


def test_missing_openrouter_key_hides_only_openrouter_models():
    policy = json.loads((ROOT / "config" / "models.json").read_text(encoding="utf-8"))
    models, warnings = generator.build_model_list(policy, {}, [])
    assert [model["name"] for model in models] == [
        "minimax-m3:cloud",
        "nemotron-3-super:cloud",
        "openai/gpt-5.6-sol",
        "openai/gpt-5.6-terra",
        "openai/gpt-5.6-luna",
        "openai/gpt-5.4-mini",
    ]
    assert len(warnings) == 5
    assert all("OPENROUTER_API_KEY" in warning for warning in warnings)


def test_generator_splits_chatgpt_from_master_key_gateway():
    policy = json.loads((ROOT / "config" / "models.json").read_text(encoding="utf-8"))
    models, _warnings = generator.build_model_list(policy, {"OPENROUTER_API_KEY": "test-key"}, ["qwen3:8b"])
    main = generator.render(models, providers={"ollama", "ollama_cloud", "openrouter"}, include_master_key=True)
    chatgpt = generator.render(models, providers={"chatgpt"}, include_master_key=False)

    assert 'model_name: "qwen3:8b"' in main
    assert 'model: "openai/qwen3:8b"' in main
    assert 'api_base: os.environ/OLLAMA_OPENAI_BASE_URL' in main
    assert 'model_name: "cofer-anthropic--qwen3:8b"' in main
    assert 'model: "ollama_chat/qwen3:8b"' in main
    assert 'api_base: os.environ/OLLAMA_BACKEND_URL' in main
    assert 'model_name: "cofer-openrouter--google/gemma-4-31b-it:free"' in main
    assert 'model_name: "google/gemma-4-31b-it:free"' not in main
    assert 'model: "openai/google/gemma-4-31b-it:free"' in main
    assert 'api_base: os.environ/OPENROUTER_API_BASE' in main
    assert 'model_name: "cofer-anthropic--google/gemma-4-31b-it:free"' in main
    assert 'model: "openrouter/google/gemma-4-31b-it:free"' in main
    assert "chatgpt/responses/" not in main
    assert "master_key: os.environ/LITELLM_MASTER_KEY" in main

    assert 'model_name: "cofer-chatgpt--gpt-5.6-luna"' in chatgpt
    assert 'model: "chatgpt/gpt-5.6-luna"' in chatgpt
    assert 'model: "chatgpt/responses/gpt-5.6-luna"' not in chatgpt
    assert "master_key" not in chatgpt
    assert "openrouter/" not in chatgpt
    assert "ollama_chat/" not in chatgpt


def test_anthropic_compatibility_deployments_are_separate_from_responses_routes():
    models = [
        {"name": "phi4:14b", "provider": "ollama", "model": "phi4:14b"},
        {
            "name": "nvidia/nemotron-3-super-120b-a12b:free",
            "provider": "openrouter",
            "model": "nvidia/nemotron-3-super-120b-a12b:free",
        },
    ]
    rendered = generator.render(models, include_master_key=True)

    assert 'model_name: "phi4:14b"' in rendered
    assert 'model: "openai/phi4:14b"' in rendered
    assert 'model_name: "cofer-anthropic--phi4:14b"' in rendered
    assert 'model: "ollama_chat/phi4:14b"' in rendered

    assert 'model_name: "cofer-openrouter--nvidia/nemotron-3-super-120b-a12b:free"' in rendered
    assert 'model: "openai/nvidia/nemotron-3-super-120b-a12b:free"' in rendered
    assert 'model_name: "cofer-anthropic--nvidia/nemotron-3-super-120b-a12b:free"' in rendered
    assert 'model: "openrouter/nvidia/nemotron-3-super-120b-a12b:free"' in rendered


def test_chatgpt_responses_prefix_is_normalized_out_of_physical_model():
    models = [
        {
            "name": "openai/gpt-5.6-luna",
            "provider": "chatgpt",
            "model": "chatgpt/responses/gpt-5.6-luna",
        }
    ]
    rendered = generator.render(models, providers={"chatgpt"}, include_master_key=False)
    assert 'model: "chatgpt/gpt-5.6-luna"' in rendered
    assert 'model: "chatgpt/responses/gpt-5.6-luna"' not in rendered
    assert 'mode: responses' in rendered
