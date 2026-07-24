# Upstream Management

Cofer One IA owns the integration layer. Headroom and LiteLLM remain third-party upstream projects.

## Pin file

`upstreams.lock.json` defines URL, ref and local path.

Current initial pins were selected when this repository scaffold was generated:

- Headroom `v0.32.0`
- LiteLLM `v1.93.0`

Do not assume those are permanently appropriate. Updates should be tested against the facade and Headroom routing path.

## Initialize

```bash
python tools/upstreams.py init
```

When the parent is a Git repository, the tool prefers real Git submodules. Otherwise it creates nested Git clones suitable for a ZIP-based installation.

## Inspect available versions

```bash
python tools/upstreams.py status
python tools/upstreams.py fetch
```

## Pin a new version

Edit `upstreams.lock.json`, then:

```bash
python tools/upstreams.py sync
./scripts/start-source.sh
./scripts/smoke-test.sh
```

Only commit a new pin after smoke/integration tests pass.

## Runtime images versus source builds

Default Compose uses version-pinned upstream container images configured in `.env` because this keeps workstation installation fast while making the starter stack reproducible. `upstreams.lock.json` pins the matching source refs for source-build mode.

`compose.source.yaml` overrides Headroom and LiteLLM to build from `upstream/` checkouts. This is useful for:

- auditing a third-party update;
- testing a patch before a release image exists;
- ensuring an exact source revision is the runtime.

## Updating image pins

When moving an upstream source ref, update the corresponding image setting in `.env.example` only after verifying that the upstream actually publishes that container tag. Source pins and runtime image tags are deliberately reviewed separately.
