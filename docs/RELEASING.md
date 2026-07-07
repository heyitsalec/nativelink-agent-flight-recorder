# Releasing NLFR

NLFR ships as a stdlib-only Python package. Releases are cut by pushing a
`v*` tag, which triggers [`.github/workflows/release.yml`](../.github/workflows/release.yml).

## What the release workflow does on a `v*` tag

1. **build** — `uv build` produces the sdist + wheel and smoke-tests the
   installed console script (`nlfr --help`, `nlfr --version`) from outside the
   source tree, then uploads `dist/` as a workflow artifact.
2. **github-release** — attaches the built `dist/*` artifacts to a GitHub
   release for the tag (auto-generated notes).
3. **pypi-publish** — publishes to PyPI via OIDC trusted publishing. **This job
   is inert (skipped) until the repo owner opts in** — see below.

The `build` and `github-release` jobs run on every `v*` tag with no extra
setup. Only PyPI publishing requires the one-time owner action.

## One-time PyPI trusted-publisher setup (owner action required)

Publishing stays **inert** until the repo owner completes all of these steps.
Until then, tagging still builds artifacts and cuts a GitHub release, but
nothing is pushed to PyPI.

1. **Register the PyPI project.** Create/claim the project
   `nativelink-agent-flight-recorder` on <https://pypi.org>.
2. **Add a trusted publisher** on the project's *Publishing* settings
   (<https://pypi.org/manage/project/nativelink-agent-flight-recorder/settings/publishing/>),
   or as a *pending* publisher before the first upload
   (<https://pypi.org/manage/account/publishing/>), with:
   - **Owner:** `heyitsalec`
   - **Repository:** `nativelink-agent-flight-recorder`
   - **Workflow filename:** `release.yml`
   - **Environment:** `pypi`
3. **Create the `pypi` GitHub environment** in this repo's
   *Settings → Environments* (optionally add release protection rules /
   required reviewers).
4. **Enable the job.** Set a **repository** variable `PYPI_PUBLISH_ENABLED=true`
   (*Settings → Secrets and variables → Actions → Variables → Repository
   variables*). The `pypi-publish` job is guarded by
   `if: vars.PYPI_PUBLISH_ENABLED == 'true'` and stays skipped until this is set.

   > **It must be a repository (or organization) variable, not an environment
   > variable.** A job-level `if:` is evaluated before the job enters its
   > `environment:`, so an env-scoped variable is invisible to the gate and the
   > publish silently skips. On v0.2.1's first tag the variable was set on the
   > `pypi` environment; the build and GitHub release succeeded while the publish
   > was skipped (issue #91). If a publish skips unexpectedly, check the
   > variable's scope first.

No API token or password is stored anywhere: authentication is short-lived
OIDC (`permissions: id-token: write`), which is why the trusted-publisher
identity above must match the workflow exactly.

## Cutting a release

```bash
# 1. Bump the version in pyproject.toml and src/nlfr/__init__.py (and the
#    --version string in src/nlfr/cli.py) to the new X.Y.Z.
# 2. Merge that to main, then tag and push:
git tag vX.Y.Z
git push origin vX.Y.Z
```

The tag push starts the workflow. Confirm the GitHub release appears with the
`dist/*` artifacts; if PyPI publishing is enabled, confirm the new version at
<https://pypi.org/p/nativelink-agent-flight-recorder>.

## Local dry run

```bash
uv build
uvx --from dist/*.whl nlfr --help      # from any directory outside the repo
uvx --from dist/*.whl nlfr --version
```
