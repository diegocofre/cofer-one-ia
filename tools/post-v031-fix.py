from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str, *, expected: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} matches, found {count}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


# Python 3.13 forbids backslashes inside f-string expressions. Keep the join
# outside the f-string in the generated gateway source.
replace(
    "services/ollama-gateway/app/main.py",
    '    prefix = f"[System instructions]\\n{\'\\n\\n\'.join(system_parts)}"\n',
    '    system_text = "\\n\\n".join(system_parts)\n    prefix = f"[System instructions]\\n{system_text}"\n',
)

# Update the pre-v0.3.1 Claude launcher contract tests rather than leaving two
# contradictory generations of the same authentication expectations.
replace(
    "services/ollama-gateway/tests/test_collama_launch.py",
    '    assert spec.env["ANTHROPIC_API_KEY"] == "cofer-one-ia"\n',
    '    assert spec.env["ANTHROPIC_AUTH_TOKEN"] == "cofer-one-ia"\n',
)
replace(
    "services/ollama-gateway/tests/test_collama_launch.py",
    '    assert "ANTHROPIC_AUTH_TOKEN" not in spec.env\n',
    '    assert "ANTHROPIC_API_KEY" not in spec.env\n',
)
replace(
    "services/ollama-gateway/tests/test_collama_launch.py",
    '    assert set(spec.unset_env) == {"ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"}\n',
    '    assert set(spec.unset_env) == {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"}\n',
)
replace(
    "services/ollama-gateway/tests/test_collama_launch.py",
    '    assert spec.env["ENABLE_TOOL_SEARCH"] == "false"\n',
    '    assert spec.env["ENABLE_TOOL_SEARCH"] == "0"\n',
)
replace(
    "services/ollama-gateway/tests/test_collama_launch.py",
    '    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "old-token")\n',
    '    monkeypatch.setenv("ANTHROPIC_API_KEY", "old-api-key")\n',
)
replace(
    "services/ollama-gateway/tests/test_collama_launch.py",
    '    assert captured["env"]["ANTHROPIC_API_KEY"] == "cofer-one-ia"\n',
    '    assert captured["env"]["ANTHROPIC_AUTH_TOKEN"] == "cofer-one-ia"\n',
)
replace(
    "services/ollama-gateway/tests/test_collama_launch.py",
    '    assert "ANTHROPIC_AUTH_TOKEN" not in captured["env"]\n',
    '    assert "ANTHROPIC_API_KEY" not in captured["env"]\n',
)

print("Applied v0.3.1 post-patch consistency fixes")
