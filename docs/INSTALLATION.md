# Installation

## Windows — recommended

### Prerequisites

Install Git, Docker Desktop, Python 3.11+ and Ollama. Pull at least one local chat model if local inference is desired.

Verify:

```powershell
git --version
docker version
docker compose version
python --version
ollama --version
ollama list
```

### Bootstrap

Run from PowerShell:

```powershell
.\scripts\bootstrap.ps1
```

Optional flags:

```powershell
# Also initialize pinned Headroom/LiteLLM source checkouts.
.\scripts\bootstrap.ps1 -WithUpstreams

# Start every dedicated Headroom client instance.
.\scripts\bootstrap.ps1 -AllClients

# Build Headroom/LiteLLM from pinned source checkouts.
.\scripts\bootstrap.ps1 -Source
```

### What changes on the host

The installer saves the current **user-level** `OLLAMA_HOST` value under:

```text
.state/ollama-host-before.json
```

It then persistently sets:

```text
OLLAMA_HOST=127.0.0.1:11435
```

This keeps the normal Ollama CLI pointed at the physical Ollama runtime rather than the virtual facade on `11434`.

For the physical server process only, Cofer One IA launches:

```text
OLLAMA_HOST=0.0.0.0:11435
```

so Docker can reach it through `host.docker.internal`.

No model files are moved or duplicated.

After bootstrap, open a **new terminal** before using commands such as:

```powershell
ollama list
ollama pull <model>
ollama rm <model>
ollama ps
```

Those commands should now operate on the physical runtime at `127.0.0.1:11435`.

### Network note

The managed physical Ollama server listens on `0.0.0.0:11435` so Docker Desktop can reach it. Use Windows Firewall to block untrusted LAN access to TCP `11435`.

The public Cofer One IA facade remains bound to `127.0.0.1:11434` by default.

### Restore

```powershell
.\scripts\restore.ps1
```

This:

1. stops Cofer One IA containers;
2. stops the Ollama server started by Cofer One IA;
3. restores the exact pre-install user-level `OLLAMA_HOST`;
4. leaves normal Ollama restart to the installed Ollama application/service.

Open a new terminal after restore.

## Linux

The shell scripts support a user-managed `ollama serve`. If Ollama is managed by systemd, configure its service explicitly before bootstrap:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11435"
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
./scripts/bootstrap.sh
```

A normal Linux Docker Engine must be able to reach the host service; loopback-only binding is usually insufficient. Restrict port `11435` with the host firewall on untrusted networks.

The project intentionally does not edit system-wide systemd units.

## Registering upstream submodules

A ZIP cannot carry Git gitlinks. If the repository was originally created from the downloadable bundle and published before registering submodules, run once:

```powershell
.\scripts\repo-init.ps1
git submodule status
git status
```

Then commit:

- `.gitmodules`
- `upstream/headroom` gitlink
- `upstream/litellm` gitlink

Future clones can then use:

```bash
git clone --recurse-submodules <repository-url>
```

## Existing Headroom installation

Cofer One IA owns port `8790` for its Cline-specific Headroom instance. Stop an existing proxy using that port before bootstrap.

Managed state lives under:

```text
data/headroom/cline/
```

Only migrate old Headroom state after confirming compatibility with the pinned Headroom version.
