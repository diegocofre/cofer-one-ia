# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_collama_only_injects_physical_host_and_forwards_arguments():
    shell = text("collama/collama")
    cmd = text("collama/collama.cmd")
    assert 'export OLLAMA_HOST="$PHYSICAL_OLLAMA_HOST"' in shell
    assert 'exec ollama "$@"' in shell
    assert "OLLAMA_HOST=http://127.0.0.1:11435" in cmd
    assert "ollama %*" in cmd


def test_bootstrap_does_not_globally_redirect_plain_ollama():
    common = text("scripts/_common.ps1")
    bootstrap = text("scripts/bootstrap.ps1")
    assert "Set-CoferOllamaClientHost" not in common + bootstrap
    assert 'SetEnvironmentVariable("OLLAMA_HOST","127.0.0.1:11435","User")' not in common + bootstrap
    assert "Migrate-LegacyOllamaHost" in bootstrap
    assert "Install-Collama" in bootstrap


def test_legacy_migration_requires_owned_state_and_preserves_custom_value():
    common = text("scripts/_common.ps1")
    assert 'ollama-host-before.json' in common
    assert "preserving it unchanged" in common
    assert "Test-LegacyCoferOllamaHost" in common


def test_chatgpt_auth_is_litellm_owned_not_codex_owned():
    compose = text("compose.yaml")
    auth = text("scripts/auth-chatgpt.sh") + text("scripts/auth-chatgpt.ps1")
    assert "CHATGPT_TOKEN_DIR: /app/chatgpt-auth" in compose
    assert "litellm.llms.chatgpt.authenticator" in auth
    assert "~/.codex" not in auth
    assert "auth.json" in auth  # only in the explicit statement that it is not read/copied


def test_postgres_is_internal_and_dashboard_is_loopback_only():
    compose = text("compose.yaml")
    postgres_block = compose.split("  postgres:", 1)[1].split("  litellm:", 1)[0]
    assert "ports:" not in postgres_block
    assert '127.0.0.1:${LITELLM_PORT:-4000}:4000' in compose
