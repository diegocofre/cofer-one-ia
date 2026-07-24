# Installation

## Windows — recommended

### Prerequisites

Install Git, Docker Desktop, Python 3.11+ and Ollama. Pull at least one local chat model if local inference is desired.

Verify:

```bash
git --version
docker version
docker compose version
python --version
ollama --version
ollama list
```

### Bootstrap

```bash
./scripts/bootstrap.sh
```

The scripts accept any working Python 3 launcher: `python3`, `python`, or `py -3`.

Optional flags:

```bash
# Also initialize the pinned Headroom/LiteLLM source checkouts.
./scripts/bootstrap.sh --with-upstreams

# Start every dedicated Headroom client instance.
./scripts/bootstrap.sh --all-clients
```

### What changes on the host

The installer saves the pre-install user `OLLAMA_HOST` value and then sets:

```text
OLLAMA_HOST=127.0.0.1:11435
```

It does not move or duplicate Ollama model files. On Windows, the persistent user value stays loopback-only so normal commands such as `ollama list` keep using `127.0.0.1:11435`. When Cofer One IA starts the physical server, that child process is launched with `OLLAMA_HOST=0.0.0.0:11435` so Docker can reach it through `host.docker.internal`.

The installer stops an incompatible Ollama listener and starts a managed `ollama serve` on `11435` when necessary. Its PID and logs are written under `.state/`. Because the server bind is Docker-reachable, use Windows Firewall to prevent untrusted LAN access to TCP `11435` if your network profile would otherwise allow it.

### Restore

```bash
./scripts/restore.sh
```

## Linux

The shell scripts support a user-managed `ollama serve`. If Ollama is managed by systemd, configure its service explicitly before running bootstrap:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11435"
```

On a normal Linux Docker Engine, the container must be able to reach the host service; binding only to loopback is usually insufficient. Restrict port `11435` with the host firewall if the machine is on an untrusted network.

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
./scripts/bootstrap.sh
```

The project does not silently edit system-wide systemd units.

## From a ZIP versus Git clone

A ZIP cannot carry Git submodule gitlinks without also carrying repository metadata. The project therefore supports both cases:

- Git checkout: upstream initializer registers true submodules.
- ZIP: upstream initializer creates nested Git checkouts from `upstreams.lock.json`.

Before publishing a freshly extracted ZIP as a new GitHub repo, use:

```bash
./scripts/repo-init.sh
```

This initializes Git and registers the upstreams as proper submodules.


## Existing Headroom installation

If another Headroom proxy already owns port `8790`, stop it before bootstrap. Cofer One IA does not stop arbitrary containers or processes automatically. Back up any existing Headroom state before migrating it into `data/headroom/cline/`.
