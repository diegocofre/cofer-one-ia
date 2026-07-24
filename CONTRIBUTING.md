# Contributing

Contributions are welcome.

## Development principles

- Keep provider choice out of client integrations.
- Keep the Ollama facade focused on protocol adaptation, not routing policy.
- Keep LiteLLM as the routing authority.
- Preserve Headroom in the inference path unless a change is explicitly diagnostic.
- Never commit secrets or generated runtime state.
- Add tests for protocol translation changes.

## Gateway tests

```bash
cd services/ollama-gateway
python -m pytest
```

## Repository checks

```bash
python -m compileall services/ollama-gateway/app tools
python tools/generate_litellm_config.py --dry-run
```

## License

By contributing, you agree that your contribution is licensed under Apache License 2.0.
