# Releasing Cofer One IA

Cofer One IA uses [Semantic Versioning](https://semver.org/) and Git tags.

## Source of truth

- `VERSION` contains the repository version without a leading `v`.
- Release tags use `v<version>`, for example `v0.3.0`.
- `CHANGELOG.md` records user-visible changes.
- GitHub Releases are created from the corresponding immutable tag.

The project is pre-1.0. Until `v1.0.0`, minor releases may contain deliberate architecture
or integration changes. Patch releases are reserved for compatible fixes.

## Release checklist

1. Start from a clean branch and confirm CI is green.
2. Choose the next SemVer version.
3. Update `VERSION` and move completed entries from `Unreleased` into a dated changelog section.
4. Run:

   ```bash
   python -m pytest services/ollama-gateway/tests
   python -m compileall services/ollama-gateway/app tools collama/collama_launch.py
   bash -n scripts/*.sh collama/collama collama/install-collama.sh
   docker compose --env-file .env -f compose.yaml config >/dev/null
   ```

5. Verify the runtime reports the same version:

   ```bash
   collama --cofer-version
   curl -s http://127.0.0.1:11434/ | python -m json.tool
   ```

6. Commit the release, then create an annotated tag:

   ```bash
   git tag -a "v$(cat VERSION)" -m "Cofer One IA v$(cat VERSION)"
   git push origin main
   git push origin "v$(cat VERSION)"
   ```

7. Create the GitHub Release from that tag. With GitHub CLI:

   ```bash
   gh release create "v$(cat VERSION)" --title "Cofer One IA v$(cat VERSION)" --generate-notes
   ```

Do not create a tag while tests are red or while `CHANGELOG.md` still describes the release
as unreleased.
