# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).resolve().parents[3]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_collama_physical_passthrough_and_universal_launch_are_separate():
    shell = text("collama/collama")
    cmd = text("collama/collama.cmd")
    sh_installer = text("collama/install-collama.sh")
    ps_installer = text("collama/install-collama.ps1")
    assert '[[ "${1:-}" == "launch" ]]' in shell
    assert "find_python3" in shell
    assert "py -3" in shell
    assert "python3" in shell
    assert "python" in shell
    assert 'export OLLAMA_HOST="$PHYSICAL_OLLAMA_HOST"' in shell
    assert 'exec ollama "$@"' in shell
    assert 'if /I "%~1"=="launch" goto launch' in cmd
    assert "OLLAMA_HOST=http://127.0.0.1:11435" in cmd
    assert "ollama %*" in cmd
    assert "collama_launch.py" in sh_installer
    assert "collama_launch.py" in ps_installer


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


def test_postgres_is_external_optional_and_dashboard_defaults_disabled():
    compose = text("compose.yaml")
    env = text(".env.example")
    bootstrap = text("scripts/bootstrap.ps1") + text("scripts/bootstrap.sh")
    assert "  postgres:" not in compose
    assert "litellm-postgres" not in compose
    assert "DATABASE_URL:" in compose
    assert "DATABASE_URL: ${" not in compose
    assert "STORE_MODEL_IN_DB: ${LITELLM_STORE_MODEL_IN_DB:-False}" in compose
    assert "DISABLE_ADMIN_UI: ${LITELLM_DISABLE_ADMIN_UI:-True}" in compose
    assert "DATABASE_URL=" not in env
    assert "LITELLM_DATABASE_URL=" not in env
    assert "LITELLM_STORE_MODEL_IN_DB=False" in env
    assert "LITELLM_DISABLE_ADMIN_UI=True" in env
    assert "ConfigurePostgres" in bootstrap
    assert "--configure-postgres" in bootstrap
    assert '127.0.0.1:${LITELLM_PORT:-4000}:4000' in compose


def test_postgres_onboarding_exists_for_both_platforms():
    ps1 = text("scripts/postgres-onboard.ps1")
    shell = text("scripts/postgres-onboard.sh")
    tool = text("tools/postgres_onboard.py")
    assert "postgres_onboard.py" in ps1
    assert "postgres_onboard.py" in shell
    assert "DATABASE_URL" in tool
    assert "migrate_database_env" in tool
    assert "LITELLM_DISABLE_ADMIN_UI" in tool
    assert "PGPASSWORD" in tool


def test_codex_headroom_proxy_is_always_on_but_profile_use_is_opt_in():
    compose = text("compose.yaml")
    disable = text("scripts/codex-direct-disable.sh") + text("scripts/codex-direct-disable.ps1")
    assert "  headroom-codex:" in compose
    assert 'profiles: ["codex-direct"]' not in compose
    assert "compose stop headroom-codex" not in disable
    assert "proxy remains running" in disable


def test_bootstrap_waits_on_readiness_and_emits_service_diagnostics():
    common = text("scripts/_common.sh")
    bootstrap = text("scripts/bootstrap.sh")
    assert "wait_service" in common
    assert "compose logs --tail=120" in common
    assert "headroom-gateway http://127.0.0.1:8790/readyz 180" in bootstrap
    assert "headroom-codex http://127.0.0.1:8787/health 180" in bootstrap


def test_reconfigure_rebuilds_gateway_image_before_recreating_services():
    shell = text("scripts/reconfigure.sh")
    ps1 = text("scripts/reconfigure.ps1")
    expected = "cupass-bridge litellm litellm-chatgpt headroom-gateway headroom-codex gateway"
    assert f"compose up -d --build --force-recreate --remove-orphans {expected}" in shell
    assert f"Invoke-CoferCompose up -d --build --force-recreate --remove-orphans {expected}" in ps1


def test_git_bash_installer_refreshes_windows_canonical_and_legacy_locations():
    installer = text("collama/install-collama.sh")
    shell = text("collama/collama")
    cmd = text("collama/collama.cmd")
    assert "MINGW*|MSYS*|CYGWIN*" in installer
    assert "CoferOneIA/bin" in installer
    assert 'legacy_dir="$HOME/.local/bin"' in installer
    assert 'install_windows_wrappers "$legacy_dir"' in installer
    assert "collama.cmd" in installer
    assert "source ~/.bashrc && hash -r" in installer
    assert '"${1:-}" == "--cofer-version"' in shell
    assert '"%~1"=="--cofer-version"' in cmd


def test_collama_validates_python_runtime_by_exact_probe_output():
    shell = text("collama/collama")
    cmd = text("collama/collama.cmd")
    common = text("scripts/_common.sh")
    installer = text("collama/install-collama.sh")
    for content in (shell, cmd, common):
        assert "COFER_PYTHON_OK" in content
    assert "Windows Store aliases are rejected" in shell
    assert "Windows Store aliases are rejected" in cmd
    assert "where python3" in cmd
    assert "COFER_PY_PROBE_FILE" in cmd
    # Installation itself must not depend on Python being runnable.
    assert "Python 3 is required to update the managed PATH entry" not in installer
    assert "awk -v marker" in installer


def test_collama_bash_rejects_false_success_python_alias(tmp_path):
    app = tmp_path / "app"
    bin_dir = tmp_path / "bin"
    app.mkdir()
    bin_dir.mkdir()
    wrapper = app / "collama"
    wrapper.write_text(text("collama/collama"), encoding="utf-8")
    wrapper.chmod(0o755)
    (app / "collama_launch.py").write_text("# placeholder\n", encoding="utf-8")

    fake_python3 = bin_dir / "python3"
    fake_python3.write_text(
        '#!/usr/bin/env bash\necho "Python was not found; Microsoft Store"\nexit 0\n',
        encoding="utf-8",
    )
    fake_python3.chmod(0o755)

    fake_python = bin_dir / "python"
    fake_python.write_text(
        '#!/usr/bin/env bash\n'
        'if [[ "$1" == "-c" ]]; then echo COFER_PYTHON_OK; exit 0; fi\n'
        'echo "REAL_PYTHON_USED:$*"\n',
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    result = subprocess.run(
        [str(wrapper), "launch", "codex", "--list"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    assert result.stdout.startswith("REAL_PYTHON_USED:")
    assert "Microsoft Store" not in result.stdout


def test_chatgpt_subscription_route_isolated_from_master_key():
    compose = text("compose.yaml")
    assert "  litellm-chatgpt:" in compose
    assert "  headroom-chatgpt:" not in compose
    chatgpt_block = compose.split("  litellm-chatgpt:", 1)[1].split("  # One client-neutral", 1)[0]
    assert "LITELLM_MASTER_KEY" not in chatgpt_block
    assert "CHATGPT_TOKEN_DIR" in chatgpt_block
    gateway_block = compose.split("  gateway:", 1)[1].split("  # Always-on escape hatch", 1)[0]
    assert "CHATGPT_GATEWAY_UPSTREAM_URL" not in gateway_block
    assert "CHATGPT_LITELLM_URL: http://litellm-chatgpt:4000" in gateway_block
    assert "litellm-chatgpt" in text("scripts/auth-chatgpt.sh")
    assert "litellm-chatgpt" in text("scripts/auth-chatgpt.ps1")


def test_repository_version_is_single_source_for_cli_bootstrap_and_gateway():
    version = text("VERSION").strip()
    parts = version.split(".")
    assert len(parts) == 3 and all(part.isdigit() for part in parts)
    assert "../VERSION" in text("collama/collama")
    assert "VERSION" in text("collama/install-collama.sh")
    assert "VERSION" in text("collama/install-collama.ps1")
    assert "$ROOT/VERSION" in text("scripts/bootstrap.sh")
    assert 'Join-Path $Root "VERSION"' in text("scripts/bootstrap.ps1")
    assert "COFER_VERSION_FILE" in text("compose.yaml")
