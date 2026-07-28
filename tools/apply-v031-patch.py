from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


def append_once(path: str, marker: str, block: str) -> None:
    text = read(path)
    if marker in text:
        return
    write(path, text.rstrip() + "\n\n" + block.rstrip() + "\n")


replace_once(
    "collama/collama_launch.py",
    '''@dataclass(frozen=True)\nclass CatalogModel:\n    name: str\n    owner: str\n''',
    '''@dataclass(frozen=True)\nclass CatalogModel:\n    name: str\n    owner: str\n    capabilities: frozenset[str] | None = None\n''',
)

replace_once(
    "collama/collama_launch.py",
    '''        # Claude Code can retain a /login-managed credential while collama is\n        # launching it against a third-party gateway.  Supplying\n        # ANTHROPIC_AUTH_TOKEN in that situation triggers Claude's token/API-key\n        # conflict detection and can make the managed credential win.  A\n        # process-scoped ANTHROPIC_API_KEY cleanly selects gateway/API-key mode;\n        # the Cofer gateway strips this client credential before adding its own\n        # internal LiteLLM authentication.\n        env = {\n            "ANTHROPIC_BASE_URL": gateway_url.rstrip("/"),\n            "ANTHROPIC_API_KEY": "cofer-one-ia",\n            "CLAUDE_CODE_ATTRIBUTION_HEADER": "0",\n            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",\n            "DISABLE_TELEMETRY": "1",\n            "DISABLE_ERROR_REPORTING": "1",\n            "DISABLE_FEEDBACK_COMMAND": "1",\n            "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",\n            # Claude's server-side ToolSearch is Anthropic-specific. Third-party\n            # providers (including many OpenRouter routes) can reject the\n            # tool_search_tool_* schema. Force standard upfront tool definitions\n            # and strip experimental beta-only fields such as defer_loading.\n            "ENABLE_TOOL_SEARCH": "false",\n            "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",\n            "ANTHROPIC_DEFAULT_OPUS_MODEL": model,\n            "ANTHROPIC_DEFAULT_SONNET_MODEL": model,\n            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,\n            "CLAUDE_CODE_SUBAGENT_MODEL": model,\n        }\n        return LaunchSpec(\n            _with_extra(["claude", "--model", model], extra_args),\n            env,\n            unset_env=("ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"),\n        )\n''',
    '''        # Anthropic documents ANTHROPIC_AUTH_TOKEN as the static bearer-token\n        # contract for Claude Code behind an LLM gateway. Keep authentication\n        # process-scoped and remove both direct API-key and OAuth credentials so\n        # an existing /login session cannot win credential precedence.\n        env = {\n            "ANTHROPIC_BASE_URL": gateway_url.rstrip("/"),\n            "ANTHROPIC_AUTH_TOKEN": "cofer-one-ia",\n            "CLAUDE_CODE_ATTRIBUTION_HEADER": "0",\n            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",\n            "DISABLE_TELEMETRY": "1",\n            "DISABLE_ERROR_REPORTING": "1",\n            "DISABLE_FEEDBACK_COMMAND": "1",\n            "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",\n            # Claude Code has shipped code paths where the experimental-beta\n            # switch alone did not suppress ToolSearch. Force ToolSearch off at\n            # the client; the gateway also sanitizes Anthropic-only tool types.\n            "ENABLE_TOOL_SEARCH": "0",\n            "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",\n            "ANTHROPIC_DEFAULT_OPUS_MODEL": model,\n            "ANTHROPIC_DEFAULT_SONNET_MODEL": model,\n            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,\n            "CLAUDE_CODE_SUBAGENT_MODEL": model,\n        }\n        return LaunchSpec(\n            _with_extra(["claude", "--model", model], extra_args),\n            env,\n            unset_env=("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"),\n        )\n''',
)

replace_once(
    "collama/collama_launch.py",
    '''def _first_existing(paths: Sequence[Path]) -> Path | None:\n    for path in paths:\n        if path.exists():\n            return path\n    return None\n\n\ndef _codex_app_candidates() -> list[Path]:\n''',
    '''def _first_existing(paths: Sequence[Path]) -> Path | None:\n    for path in paths:\n        if path.exists():\n            return path\n    return None\n\n\ndef _windows_start_apps() -> list[tuple[str, str]]:\n    """Return Start-menu app names and AppUserModelIDs for the current user."""\n    powershell = (\n        shutil.which("pwsh.exe")\n        or shutil.which("powershell.exe")\n        or shutil.which("pwsh")\n        or shutil.which("powershell")\n    )\n    if powershell is None:\n        return []\n    command = [\n        powershell,\n        "-NoLogo",\n        "-NoProfile",\n        "-NonInteractive",\n        "-Command",\n        "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress",\n    ]\n    try:\n        completed = subprocess.run(\n            command,\n            check=False,\n            capture_output=True,\n            text=True,\n            timeout=10,\n        )\n    except (OSError, subprocess.TimeoutExpired):\n        return []\n    if completed.returncode != 0 or not completed.stdout.strip():\n        return []\n    try:\n        payload = json.loads(completed.stdout)\n    except json.JSONDecodeError:\n        return []\n    rows = [payload] if isinstance(payload, dict) else payload if isinstance(payload, list) else []\n    result: list[tuple[str, str]] = []\n    for row in rows:\n        if not isinstance(row, dict):\n            continue\n        name = row.get("Name")\n        app_id = row.get("AppID")\n        if isinstance(name, str) and name.strip() and isinstance(app_id, str) and app_id.strip():\n            result.append((name.strip(), app_id.strip()))\n    return result\n\n\ndef _windows_start_app_id(preferred_names: Sequence[str]) -> str | None:\n    apps = _windows_start_apps()\n    for preferred in preferred_names:\n        wanted = preferred.casefold()\n        for name, app_id in apps:\n            if name.casefold() == wanted:\n                return app_id\n    return None\n\n\ndef _codex_app_candidates() -> list[Path]:\n''',
)

replace_once(
    "collama/collama_launch.py",
    '''def _launch_desktop_app(candidates: Sequence[Path], mac_name: str) -> LaunchSpec:\n    if _is_macos():\n        app = _first_existing(candidates)\n        return LaunchSpec(["open", str(app)]) if app is not None else LaunchSpec(["open", "-a", mac_name])\n    if _is_windows():\n        executable = _first_existing(candidates)\n        if executable is None:\n            raise LauncherError(f"{mac_name} executable was not found")\n        return LaunchSpec([str(executable)])\n    raise LauncherError(f"{mac_name} launch is supported only on Windows and macOS")\n''',
    '''def _launch_desktop_app(\n    candidates: Sequence[Path],\n    mac_name: str,\n    windows_app_names: Sequence[str] = (),\n) -> LaunchSpec:\n    if _is_macos():\n        app = _first_existing(candidates)\n        return LaunchSpec(["open", str(app)]) if app is not None else LaunchSpec(["open", "-a", mac_name])\n    if _is_windows():\n        executable = _first_existing(candidates)\n        if executable is not None:\n            return LaunchSpec([str(executable)])\n        app_id = _windows_start_app_id(windows_app_names)\n        if app_id is not None:\n            return LaunchSpec(["explorer.exe", f"shell:AppsFolder\\\\{app_id}"])\n        searched = ", ".join(windows_app_names) or mac_name\n        raise LauncherError(f"{mac_name} executable/Start app was not found (searched: {searched})")\n    raise LauncherError(f"{mac_name} launch is supported only on Windows and macOS")\n''',
)
replace_once(
    "collama/collama_launch.py",
    '        return _launch_desktop_app(_codex_app_candidates(), "ChatGPT")\n',
    '        return _launch_desktop_app(_codex_app_candidates(), "ChatGPT", ("ChatGPT", "Codex"))\n',
)
replace_once(
    "collama/collama_launch.py",
    '        return _launch_desktop_app(_claude_desktop_candidates(), "Claude")\n',
    '        return _launch_desktop_app(_claude_desktop_candidates(), "Claude", ("Claude", "Claude Desktop"))\n',
)
replace_once(
    "collama/collama_launch.py",
    '''ALIASES = {\n    "claude-code": "claude",\n    "copilot-cli": "copilot",\n    "qwen-code": "qwen",\n}\n''',
    '''ALIASES = {\n    "claude-code": "claude",\n    "claudedesktop": "claude-desktop",\n    "codexapp": "codex-app",\n    "copilot-cli": "copilot",\n    "qwen-code": "qwen",\n}\n''',
)
replace_once(
    "collama/collama_launch.py",
    '''def catalog_group(model: CatalogModel) -> str:\n    owner = model.owner.casefold()\n    if owner in {"ollama-cloud", "ollama_cloud"}:\n        return "Ollama Cloud"\n    if owner in {"ollama", "local"}:\n        return "Local"\n    if owner == "openrouter":\n        return "OpenRouter"\n    if owner in {"chatgpt", "openai"}:\n        return "OpenAI"\n    if model.name.startswith("openai/"):\n        return "OpenAI"\n    if model.name.endswith(":cloud") and "/" not in model.name:\n        return "Ollama Cloud"\n    if "/" in model.name or model.name == "openrouter-auto":\n        return "OpenRouter"\n    return "Local"\n\n\ndef grouped_catalog(models: Sequence[CatalogModel]) -> list[tuple[str, list[CatalogModel]]]:\n''',
    '''def catalog_group(model: CatalogModel) -> str:\n    owner = model.owner.casefold()\n    if owner in {"ollama-cloud", "ollama_cloud"}:\n        return "Ollama Cloud"\n    if owner in {"ollama", "local"}:\n        return "Local"\n    if owner == "openrouter":\n        return "OpenRouter"\n    if owner in {"chatgpt", "openai"}:\n        return "OpenAI"\n    if model.name.startswith("openai/"):\n        return "OpenAI"\n    if model.name.endswith(":cloud") and "/" not in model.name:\n        return "Ollama Cloud"\n    if "/" in model.name or model.name == "openrouter-auto":\n        return "OpenRouter"\n    return "Local"\n\n\ndef fetch_model_capabilities(\n    gateway_url: str,\n    model: CatalogModel,\n    timeout: float = DEFAULT_TIMEOUT_SECONDS,\n) -> CatalogModel:\n    """Probe the gateway's Ollama-compatible show endpoint for model capabilities."""\n    url = f"{gateway_url.rstrip('/')}/api/show"\n    body = json.dumps({"model": model.name}).encode("utf-8")\n    request = urllib.request.Request(\n        url,\n        data=body,\n        method="POST",\n        headers={"Accept": "application/json", "Content-Type": "application/json"},\n    )\n    try:\n        with urllib.request.urlopen(request, timeout=timeout) as response:\n            payload = json.load(response)\n    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):\n        return model\n    capabilities = payload.get("capabilities") if isinstance(payload, dict) else None\n    if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):\n        return model\n    return CatalogModel(model.name, model.owner, frozenset(item.casefold() for item in capabilities))\n\n\ndef claude_compatible_models(models: Sequence[CatalogModel], gateway_url: str) -> list[CatalogModel]:\n    """Keep Claude Code models that are known to support client-side tools.\n\n    Local/Ollama Cloud models are probed from physical Ollama through the\n    gateway. Remote providers remain fail-open because their capabilities are\n    provider-managed and a missing capability probe must not hide valid routes.\n    """\n    result: list[CatalogModel] = []\n    for item in models:\n        candidate = fetch_model_capabilities(gateway_url, item) if catalog_group(item) in {"Local", "Ollama Cloud"} else item\n        if candidate.capabilities is None or "tools" in candidate.capabilities:\n            result.append(candidate)\n    return result\n\n\ndef grouped_catalog(models: Sequence[CatalogModel]) -> list[tuple[str, list[CatalogModel]]]:\n''',
)
replace_once(
    "collama/collama_launch.py",
    '''    models = fetch_catalog(gateway_url)\n    names = {item.name for item in models}\n    if list_only:\n        print_catalog(models, adapter.display_name)\n        return 0\n\n    selected = model or choose_model(models, adapter.display_name)\n    if selected not in names:\n        raise LauncherError(\n            f"model '{selected}' is not published by Cofer One IA. "\n            f"Run 'collama launch {client} --list' to see the active catalog."\n        )\n''',
    '''    models = fetch_catalog(gateway_url)\n    published_names = {item.name for item in models}\n    if client == "claude":\n        models = claude_compatible_models(models, gateway_url)\n    compatible_names = {item.name for item in models}\n    if list_only:\n        print_catalog(models, adapter.display_name)\n        return 0\n\n    selected = model or choose_model(models, adapter.display_name)\n    if selected not in published_names:\n        raise LauncherError(\n            f"model '{selected}' is not published by Cofer One IA. "\n            f"Run 'collama launch {client} --list' to see the active catalog."\n        )\n    if selected not in compatible_names:\n        raise LauncherError(\n            f"model '{selected}' is not compatible with {adapter.display_name}: "\n            "the model does not advertise the 'tools' capability"\n        )\n''',
)

replace_once(
    "services/ollama-gateway/app/config.py",
    '''    chatgpt_litellm_url: str = os.getenv("CHATGPT_LITELLM_URL", "http://litellm-chatgpt:4000").rstrip("/")\n    litellm_master_key: str = os.getenv("LITELLM_MASTER_KEY", "")\n''',
    '''    chatgpt_litellm_url: str = os.getenv("CHATGPT_LITELLM_URL", "http://litellm-chatgpt:4000").rstrip("/")\n    ollama_backend_url: str = os.getenv("OLLAMA_BACKEND_URL", "http://host.docker.internal:11435").rstrip("/")\n    litellm_master_key: str = os.getenv("LITELLM_MASTER_KEY", "")\n''',
)
replace_once(
    "compose.yaml",
    '''      CHATGPT_LITELLM_URL: http://litellm-chatgpt:4000\n      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}\n''',
    '''      CHATGPT_LITELLM_URL: http://litellm-chatgpt:4000\n      OLLAMA_BACKEND_URL: ${OLLAMA_BACKEND_URL:-http://host.docker.internal:11435}\n      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}\n''',
)
replace_once(
    "services/ollama-gateway/app/main.py",
    '''def _chatgpt_compatible_anthropic_payload(payload: dict[str, Any]) -> dict[str, Any]:\n    """Adapt Claude Messages payloads to ChatGPT subscription constraints.\n\n    ChatGPT's Codex backend rejects system-role messages. LiteLLM maps the\n    Anthropic top-level ``system`` field to that forbidden role, so for this\n    provider only we preserve the instructions as the first user content\n    instead. All tool/message blocks remain otherwise untouched.\n    """\n    system_text = _anthropic_system_text(payload.get("system"))\n    if not system_text:\n        return payload\n\n    result = dict(payload)\n    result.pop("system", None)\n    messages = result.get("messages")\n    messages = (\n        [dict(item) if isinstance(item, dict) else item for item in messages]\n        if isinstance(messages, list)\n        else []\n    )\n    prefix = f"[System instructions]\\n{system_text}"\n\n    for index, message in enumerate(messages):\n        if not isinstance(message, dict) or message.get("role") != "user":\n            continue\n        content = message.get("content")\n        updated = dict(message)\n        if isinstance(content, str):\n            updated["content"] = f"{prefix}\\n\\n[User message]\\n{content}"\n        elif isinstance(content, list):\n            updated["content"] = [{"type": "text", "text": prefix}, *content]\n        else:\n            updated["content"] = prefix\n        messages[index] = updated\n        result["messages"] = messages\n        return result\n\n    result["messages"] = [{"role": "user", "content": prefix}, *messages]\n    return result\n''',
    '''def _chatgpt_compatible_anthropic_payload(payload: dict[str, Any]) -> dict[str, Any]:\n    """Adapt Claude Messages payloads to ChatGPT subscription constraints.\n\n    The ChatGPT/Codex Responses backend rejects system-role messages. Normalize\n    both Anthropic's top-level ``system`` field and defensive system-role\n    message variants into the first user turn before LiteLLM translates the\n    request.\n    """\n    result = dict(payload)\n    system_parts: list[str] = []\n    top_level = _anthropic_system_text(payload.get("system"))\n    if top_level:\n        system_parts.append(top_level)\n    result.pop("system", None)\n\n    raw_messages = result.get("messages")\n    messages: list[Any] = []\n    if isinstance(raw_messages, list):\n        for item in raw_messages:\n            if not isinstance(item, dict):\n                messages.append(item)\n                continue\n            message = dict(item)\n            if message.get("role") == "system":\n                text = _anthropic_system_text(message.get("content"))\n                if text:\n                    system_parts.append(text)\n                continue\n            messages.append(message)\n\n    if not system_parts:\n        return payload\n\n    prefix = f"[System instructions]\\n{'\\n\\n'.join(system_parts)}"\n    for index, message in enumerate(messages):\n        if not isinstance(message, dict) or message.get("role") != "user":\n            continue\n        content = message.get("content")\n        updated = dict(message)\n        if isinstance(content, str):\n            updated["content"] = f"{prefix}\\n\\n[User message]\\n{content}"\n        elif isinstance(content, list):\n            updated["content"] = [{"type": "text", "text": prefix}, *content]\n        else:\n            updated["content"] = prefix\n        messages[index] = updated\n        result["messages"] = messages\n        return result\n\n    result["messages"] = [{"role": "user", "content": prefix}, *messages]\n    return result\n''',
)
replace_once(
    "services/ollama-gateway/app/main.py",
    '''def _anthropic_main_compatible_payload(payload: dict[str, Any]) -> dict[str, Any]:\n    """Normalize Claude controls for main-router providers.\n\n    Claude Code sends adaptive/extended-thinking controls even when the chosen\n    local Ollama model does not implement thinking. Ollama rejects those\n    controls rather than silently ignoring them. For physical local models we\n    preserve thinking only for known thinking-capable families; remote routes\n    are left untouched and provider/LiteLLM capability handling applies.\n    """\n    model = payload.get("model")\n    if not isinstance(model, str):\n        return payload\n    resolved = resolve_launch_alias(model)\n    is_physical_local = "/" not in resolved and not resolved.endswith(":cloud")\n    if not is_physical_local or _local_ollama_supports_thinking(resolved):\n        return payload\n\n    result = dict(payload)\n    result.pop("thinking", None)\n    result.pop("reasoning_effort", None)\n    output_config = result.get("output_config")\n    if isinstance(output_config, dict) and "effort" in output_config:\n        normalized_output = dict(output_config)\n        normalized_output.pop("effort", None)\n        if normalized_output:\n            result["output_config"] = normalized_output\n        else:\n            result.pop("output_config", None)\n    return result\n''',
    '''def _anthropic_main_compatible_payload(payload: dict[str, Any]) -> dict[str, Any]:\n    """Normalize Claude controls for non-Anthropic main-router providers.\n\n    ToolSearch is an Anthropic server-side tool family and must not reach\n    Ollama/OpenRouter providers. Standard client-side tools are preserved, with\n    beta-only ``defer_loading`` metadata removed. Local non-thinking models also\n    have Claude's adaptive reasoning controls removed.\n    """\n    result = dict(payload)\n    tools = result.get("tools")\n    if isinstance(tools, list):\n        normalized_tools: list[Any] = []\n        for tool in tools:\n            if not isinstance(tool, dict):\n                normalized_tools.append(tool)\n                continue\n            tool_type = tool.get("type")\n            if isinstance(tool_type, str) and tool_type.startswith("tool_search_tool_"):\n                continue\n            normalized = dict(tool)\n            normalized.pop("defer_loading", None)\n            normalized_tools.append(normalized)\n        if normalized_tools:\n            result["tools"] = normalized_tools\n        else:\n            result.pop("tools", None)\n\n    model = result.get("model")\n    if not isinstance(model, str):\n        return result\n    resolved = resolve_launch_alias(model)\n    is_physical_local = "/" not in resolved and not resolved.endswith(":cloud")\n    if not is_physical_local or _local_ollama_supports_thinking(resolved):\n        return result\n\n    result.pop("thinking", None)\n    result.pop("reasoning_effort", None)\n    output_config = result.get("output_config")\n    if isinstance(output_config, dict) and "effort" in output_config:\n        normalized_output = dict(output_config)\n        normalized_output.pop("effort", None)\n        if normalized_output:\n            result["output_config"] = normalized_output\n        else:\n            result.pop("output_config", None)\n    return result\n''',
)
replace_once(
    "services/ollama-gateway/app/main.py",
    '''@app.post("/api/show")\nasync def show(request: Request) -> dict[str, Any]:\n    body = await request.json()\n    name = body.get("name") or body.get("model")\n    if not name:\n        raise HTTPException(status_code=400, detail="name/model is required")\n    if name not in await _models():\n        raise HTTPException(status_code=404, detail=f"unknown model: {name}")\n    return {\n        "license": "Provider/model specific",\n        "modelfile": "# Virtual model routed by Cofer One IA",\n        "parameters": "",\n        "template": "",\n        "details": {"family": "cofer-one-ia", "families": ["cofer-one-ia"]},\n        "model_info": {"cofer.context_length": settings.default_context_length},\n        "capabilities": ["completion", "tools"],\n    }\n''',
    '''async def _physical_ollama_show(name: str) -> dict[str, Any] | None:\n    """Return physical Ollama metadata when it is reachable and authoritative."""\n    try:\n        async with httpx.AsyncClient(timeout=3) as client:\n            response = await client.post(f"{settings.ollama_backend_url}/api/show", json={"model": name})\n            if not response.is_success:\n                return None\n            payload = response.json()\n    except (httpx.HTTPError, ValueError):\n        return None\n    return payload if isinstance(payload, dict) else None\n\n\n@app.post("/api/show")\nasync def show(request: Request) -> dict[str, Any]:\n    body = await request.json()\n    name = body.get("name") or body.get("model")\n    if not name:\n        raise HTTPException(status_code=400, detail="name/model is required")\n    if name not in await _models():\n        raise HTTPException(status_code=404, detail=f"unknown model: {name}")\n\n    if _model_owner(name) in {"ollama", "ollama-cloud"}:\n        physical = await _physical_ollama_show(name)\n        if physical is not None:\n            return physical\n\n    return {\n        "license": "Provider/model specific",\n        "modelfile": "# Virtual model routed by Cofer One IA",\n        "parameters": "",\n        "template": "",\n        "details": {"family": "cofer-one-ia", "families": ["cofer-one-ia"]},\n        "model_info": {"cofer.context_length": settings.default_context_length},\n        "capabilities": ["completion", "tools"],\n    }\n''',
)

append_once(
    "services/ollama-gateway/tests/test_collama_launch.py",
    "def test_v031_claude_uses_gateway_bearer_token_contract():",
    r'''def test_v031_claude_uses_gateway_bearer_token_contract():
    model = CatalogModel("openai/gpt-5.6-luna", "chatgpt")
    spec = MODULE.ClaudeAdapter().build(model.name, [model], "http://127.0.0.1:11434", [])
    assert spec.env["ANTHROPIC_AUTH_TOKEN"] == "cofer-one-ia"
    assert "ANTHROPIC_API_KEY" not in spec.env
    assert set(spec.unset_env) == {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"}
    assert spec.env["ENABLE_TOOL_SEARCH"] == "0"


def test_v031_claude_filters_local_models_without_tools(monkeypatch, capsys):
    models = [CatalogModel("phi4:14b", "ollama"), CatalogModel("qwen3-coder:30b", "ollama")]
    monkeypatch.setattr(MODULE, "fetch_catalog", lambda *_args, **_kwargs: models)

    def capabilities(_gateway, model, timeout=MODULE.DEFAULT_TIMEOUT_SECONDS):
        caps = {"phi4:14b": frozenset({"completion"}), "qwen3-coder:30b": frozenset({"completion", "tools"})}
        return CatalogModel(model.name, model.owner, caps[model.name])

    monkeypatch.setattr(MODULE, "fetch_model_capabilities", capabilities)
    rc = MODULE.launch_client(
        "claude",
        gateway_url="http://127.0.0.1:11434",
        model=None,
        list_only=True,
        dry_run=False,
        extra_args=[],
    )
    assert rc == 0
    output = capsys.readouterr().out
    assert "qwen3-coder:30b" in output
    assert "phi4:14b" not in output


def test_v031_claude_rejects_explicit_local_model_without_tools(monkeypatch):
    model = CatalogModel("phi4:14b", "ollama")
    monkeypatch.setattr(MODULE, "fetch_catalog", lambda *_args, **_kwargs: [model])
    monkeypatch.setattr(
        MODULE,
        "fetch_model_capabilities",
        lambda _gateway, item, timeout=MODULE.DEFAULT_TIMEOUT_SECONDS: CatalogModel(item.name, item.owner, frozenset({"completion"})),
    )
    with pytest.raises(MODULE.LauncherError, match="does not advertise the 'tools' capability"):
        MODULE.launch_client(
            "claude",
            gateway_url="http://127.0.0.1:11434",
            model="phi4:14b",
            list_only=False,
            dry_run=True,
            extra_args=[],
        )


def test_v031_windows_desktop_apps_fall_back_to_start_menu(monkeypatch):
    monkeypatch.setattr(MODULE, "_is_windows", lambda: True)
    monkeypatch.setattr(MODULE, "_is_macos", lambda: False)
    monkeypatch.setattr(MODULE, "_first_existing", lambda _paths: None)
    monkeypatch.setattr(
        MODULE,
        "_windows_start_apps",
        lambda: [("ChatGPT", "OpenAI.ChatGPT_123!App"), ("Claude", "Anthropic.Claude_456!App")],
    )

    codex = MODULE.CodexAppAdapter().build("openai/gpt-5.6-luna", [], "http://127.0.0.1:11434", [])
    claude = MODULE.ClaudeDesktopAdapter().build("openai/gpt-5.6-luna", [], "http://127.0.0.1:11434", [])

    assert codex.command == ["explorer.exe", r"shell:AppsFolder\OpenAI.ChatGPT_123!App"]
    assert claude.command == ["explorer.exe", r"shell:AppsFolder\Anthropic.Claude_456!App"]


def test_v031_desktop_aliases_are_accepted():
    assert MODULE.canonical_client("codexapp") == "codex-app"
    assert MODULE.canonical_client("claudedesktop") == "claude-desktop"
''',
)
append_once(
    "services/ollama-gateway/tests/test_upstream_proxy.py",
    "async def test_v031_openrouter_anthropic_strips_toolsearch_schema(client):",
    r'''@pytest.mark.asyncio
async def test_v031_openrouter_anthropic_strips_toolsearch_schema(client):
    FakeAsyncClient.response = FakeResponse()
    payload = {
        "model": "nvidia/nemotron-3-super-120b-a12b:free",
        "messages": [{"role": "user", "content": "read the repository"}],
        "tools": [
            {"type": "tool_search_tool_regex_20251119", "name": "ToolSearch"},
            {
                "name": "Read",
                "description": "Read a file",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                "defer_loading": True,
            },
        ],
    }
    response = await client.post("/v1/messages", json=payload)
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert forwarded["model"] == "cofer-anthropic--nvidia/nemotron-3-super-120b-a12b:free"
    assert len(forwarded["tools"]) == 1
    assert forwarded["tools"][0]["name"] == "Read"
    assert "defer_loading" not in forwarded["tools"][0]
    assert forwarded["tools"][0]["input_schema"]["type"] == "object"


@pytest.mark.asyncio
async def test_v031_chatgpt_interactive_system_roles_are_folded_into_user_content(client):
    FakeAsyncClient.response = FakeResponse()
    payload = {
        "model": "openai/gpt-5.6-luna",
        "system": [{"type": "text", "text": "Top-level Claude Code instructions"}],
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": "Interactive session instructions"}]},
            {"role": "user", "content": "Which model are we using?"},
        ],
    }
    response = await client.post("/v1/messages", json=payload)
    assert response.status_code == 200
    call = FakeAsyncClient.instances[-1].calls[0]
    forwarded = __import__("json").loads(call[2]["content"])
    assert "system" not in forwarded
    assert all(message.get("role") != "system" for message in forwarded["messages"] if isinstance(message, dict))
    first = forwarded["messages"][0]
    assert first["role"] == "user"
    assert "Top-level Claude Code instructions" in first["content"]
    assert "Interactive session instructions" in first["content"]
    assert "Which model are we using?" in first["content"]


@pytest.mark.asyncio
async def test_v031_api_show_uses_physical_ollama_capabilities_for_local_models(monkeypatch, client):
    async def fake_models(force=False):
        return ["phi4:14b"]

    async def fake_show(name):
        assert name == "phi4:14b"
        return {"model": name, "capabilities": ["completion"]}

    monkeypatch.setattr(main_module, "_models", fake_models)
    monkeypatch.setattr(main_module, "_physical_ollama_show", fake_show)
    response = await client.post("/api/show", json={"model": "phi4:14b"})
    assert response.status_code == 200
    assert response.json()["capabilities"] == ["completion"]
''',
)

replace_once("VERSION", "0.3.0", "0.3.1")
replace_once(
    "CHANGELOG.md",
    '''## [Unreleased]\n\n## [0.3.0] - 2026-07-27\n''',
    '''## [Unreleased]\n\n## [0.3.1] - 2026-07-28\n\n### Fixed\n\n- Claude Code gateway authentication now uses Anthropic's documented `ANTHROPIC_AUTH_TOKEN` bearer contract while clearing inherited API-key/OAuth credentials.\n- Claude ToolSearch/deferred-tool beta schemas are disabled client-side and sanitized at the gateway before Ollama/OpenRouter forwarding.\n- ChatGPT-subscription Claude requests normalize both top-level and message-level system instructions into user content for Responses compatibility.\n- Claude model selection probes physical Ollama `/api/show` capabilities and hides/rejects local or cloud models that explicitly lack `tools`.\n- Windows Codex/ChatGPT and Claude Desktop launching falls back to Start-menu AppUserModelIDs when no stable executable path exists.\n- Added `codexapp` and `claudedesktop` launcher aliases.\n- Added regression contracts for the observed Claude auth, ToolSearch, system-role, capability-filter and Windows packaged-app failures.\n\n## [0.3.0] - 2026-07-27\n''',
)
replace_once(
    "CHANGELOG.md",
    '''[Unreleased]: https://github.com/diegocofre/cofer-one-ia/compare/v0.3.0...HEAD\n[0.3.0]: https://github.com/diegocofre/cofer-one-ia/compare/v0.2.0...v0.3.0\n''',
    '''[Unreleased]: https://github.com/diegocofre/cofer-one-ia/compare/v0.3.1...HEAD\n[0.3.1]: https://github.com/diegocofre/cofer-one-ia/compare/v0.3.0...v0.3.1\n[0.3.0]: https://github.com/diegocofre/cofer-one-ia/compare/v0.2.0...v0.3.0\n''',
)
replace_once(
    "docs/OLLAMA-LAUNCH.md",
    'Aliases: `claude-code`, `copilot-cli`, `qwen-code`.\n',
    'Aliases: `claude-code`, `claudedesktop`, `codexapp`, `copilot-cli`, `qwen-code`.\n',
)
replace_once(
    "docs/OLLAMA-LAUNCH.md",
    '''- Claude Code uses a process-scoped `ANTHROPIC_BASE_URL` plus a Cofer-only\n  `ANTHROPIC_API_KEY`. `collama` removes inherited `ANTHROPIC_AUTH_TOKEN` and\n  `CLAUDE_CODE_OAUTH_TOKEN` values for that child process so an existing\n  Claude `/login` session cannot conflict with gateway authentication.\n''',
    '''- Claude Code uses a process-scoped `ANTHROPIC_BASE_URL` plus the documented\n  gateway bearer contract in `ANTHROPIC_AUTH_TOKEN`. `collama` removes inherited\n  `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` values for that child process\n  so an existing Claude `/login` session cannot conflict with gateway authentication.\n''',
)
replace_once(
    "docs/OLLAMA-LAUNCH.md",
    '''For third-party compatibility, `collama launch claude` forces `ENABLE_TOOL_SEARCH=false`\nand `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`. Claude Code therefore sends ordinary\ntool definitions instead of Anthropic-only server-side ToolSearch types and beta-only\n`defer_loading` fields that non-Anthropic providers may reject.\n''',
    '''For third-party compatibility, `collama launch claude` forces `ENABLE_TOOL_SEARCH=0`\nand `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`. The gateway independently removes\nAnthropic-only `tool_search_tool_*` definitions and beta-only `defer_loading` metadata\nbefore Ollama/OpenRouter forwarding. For Local and Ollama Cloud models, the launcher\nalso probes `/api/show`; models that explicitly lack the `tools` capability are omitted\nfrom Claude's selector and rejected when named explicitly.\n''',
)
replace_once(
    "docs/OLLAMA-LAUNCH.md",
    '''Codex App is supported on Windows and macOS.\n''',
    '''Codex App is supported on Windows and macOS. On Windows the launcher first checks\nknown executable locations, then resolves the installed ChatGPT/Codex Start-menu\nAppUserModelID so Microsoft Store/MSIX installations can be launched without a stable EXE path.\n''',
)
replace_once(
    "docs/OLLAMA-LAUNCH.md",
    '''Claude Desktop is supported on Windows and macOS. Always keep the backup state\nuntil the integration has been verified locally, and use `--restore` to return\nto the pre-Cofer profile.\n''',
    '''Claude Desktop is supported on Windows and macOS. On Windows, executable lookup\nfalls back to the installed Start-menu AppUserModelID for packaged/MSIX builds. Always\nkeep the backup state until the integration has been verified locally, and use\n`--restore` to return to the pre-Cofer profile.\n''',
)

print("Applied Cofer One IA v0.3.1 compatibility patch")
