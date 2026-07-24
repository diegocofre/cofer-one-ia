# Publishing as a GitHub Repository

Headroom and LiteLLM should be represented as true Git submodules in the public repository.

## Register submodules

Windows PowerShell:

```powershell
.\scripts\repo-init.ps1
git submodule status
git status
```

Linux/macOS:

```bash
./scripts/repo-init.sh
git submodule status
git status
```

Commit the resulting:

- `.gitmodules`
- `upstream/headroom` gitlink
- `upstream/litellm` gitlink

A normal clone should then use:

```bash
git clone --recurse-submodules <repository-url>
```

or:

```bash
git submodule update --init --recursive
```

## Before tagging a release

Run unit/config checks and, on a machine with Ollama + Docker, end-to-end validation.

Windows:

```powershell
python -m compileall services/ollama-gateway/app tools
python -m pytest services/ollama-gateway/tests
.\scripts\doctor.ps1
.\scripts\smoke-test.ps1
```

Linux:

```bash
python -m compileall services/ollama-gateway/app tools
python -m pytest services/ollama-gateway/tests
./scripts/doctor.sh
./scripts/smoke-test.sh
```

Remote-provider smoke tests should be run explicitly rather than as the default validation path.

For every upstream bump:

1. update `upstreams.lock.json`;
2. update the matching runtime image pin in `.env.example`/Compose;
3. initialize/sync the source checkout;
4. test source mode;
5. run gateway and end-to-end tests;
6. commit the source ref and image pin together.

Never publish a release with `latest` as a default third-party runtime image.
