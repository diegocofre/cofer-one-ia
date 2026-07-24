# Publishing as a GitHub Repository

The downloadable project intentionally does not embed the full Headroom and LiteLLM histories. Initialize the Git repository before the first public commit so both upstreams become proper Git submodules.

```bash
cd cofer-one-ia
./scripts/repo-init.sh

git status
git add .
git commit -m "Initial Cofer One IA release"
```

Then create the GitHub repository and push normally.

After initialization, verify:

```bash
git submodule status
```

A normal clone should then use:

```bash
git clone --recurse-submodules <repository-url>
```

or, after an ordinary clone:

```bash
git submodule update --init --recursive
```

## Before tagging a release

Run the unit/config checks and, on a machine with Ollama + Docker, the end-to-end smoke test:

```bash
python -m compileall services/ollama-gateway/app tools
python -m pytest services/ollama-gateway/tests
./scripts/doctor.sh
./scripts/smoke-test.sh
```

For an upstream bump, also test source mode before changing the lock file in a release commit.
