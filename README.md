# repo-drift

`repo-drift` is a small, configurable validator for repository claims and
configuration. It emits standard GitHub Actions workflow commands when run
with `--reporter github`, so errors appear as inline annotations.

The package has no credentials, network SDK, telemetry, or private package
dependency. The `visibility` and `branch_name` checks optionally invoke the
locally authenticated `gh` command only when their rules require repository
metadata; failures become warnings instead of failing a workflow.

## Purpose

Catches a repo's documentation and config drifting away from what it
actually claims: a stale default branch name in the docs, a dependency
named in prose but missing from the manifest, a visibility mismatch, a
required file that went missing. Consumed as a GitHub Action in CI or as
a standalone CLI for a local check.

## Install

```bash
python -m pip install repo-drift
```

Or pin the GitHub Action (see below) without installing anything locally.

## GitHub Action

Check out the repository before using the action:

```yaml
name: Drift
on: [pull_request]

jobs:
  drift:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: alawein/repo-drift@v0.1.0
```

For supply-chain pinning, downstream repositories should replace the tag with
the immutable commit SHA for `v0.1.0` after verifying it.

Inputs:

- `working-directory`: repository directory relative to `$GITHUB_WORKSPACE`
  (default: `.`).
- `rules`: optional rules file relative to `$GITHUB_WORKSPACE`.
- `detectors`: optional comma-separated detector list.

The action installs the checked-out action source at `$GITHUB_ACTION_PATH` and
runs `repo-drift check --reporter github`; it does not require a token or any
private dependency.

## CLI

```bash
python -m pip install repo-drift
repo-drift check --reporter github
repo-drift explain
```

`repo-drift check` reads `.drift-rules.yaml` from the target directory by
default. Use `--target PATH` or `--rules PATH` to override that behavior.
Errors return exit status 1; warnings and notices return 0.

## Rules

```yaml
opt_out:
  - visibility

detector_config:
  branch_name:
    expected: main
  claimed_dep:
    tracked_packages:
      js: [example-sdk]
      py: [example-sdk]
  feature_claim:
    src_dirs: [src]
    claims:
      - tokens: [webhook]
        description: Webhook delivery
  missing_file:
    required: [README.md, SECURITY.md]
    schemas:
      config/service.yaml: schemas/service.schema.json
  stale_config:
    config_map:
      tool.config.js: [tool-package]
  visibility:
    expected: public
```

Detectors:

- `branch_name`: finds stale branch references in common documentation files.
  Set `expected` or allow it to read the default branch with `gh`.
- `claimed_dep`: flags tracked SDK/package names documented without a matching
  JavaScript or Python dependency manifest entry.
- `feature_claim`: flags configured documentation claims without matching
  source tokens.
- `missing_file`: checks configured required files and validates YAML/JSON
  targets against repository-local JSON Schema files.
- `stale_config`: detects common JavaScript framework config files whose
  package is absent from `package.json`.
- `visibility`: compares configured public/private visibility with GitHub.

`schemas` deliberately points to JSON Schema files in the repository being
checked; repo-drift includes no organization-specific metadata schema.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
python -m build
```

## Architecture

- `src/repo_drift/cli.py`, `__main__.py`: entry points for `repo-drift check`
  and `repo-drift explain`.
- `src/repo_drift/runner.py`, `rules.py`: load `.drift-rules.yaml` and run the
  configured detectors against the target directory.
- `src/repo_drift/detectors/`: one module per detector (`branch_name`,
  `claimed_dep`, `feature_claim`, `missing_file`, `stale_config`,
  `visibility`); see `registry.py` for how they're wired up.
- `src/repo_drift/reporters.py`, `finding.py`: turn detector results into
  plain-text or GitHub Actions annotation output.
- `src/repo_drift/_github.py`: the only network path, used solely by the
  `visibility` and `branch_name` detectors' optional `gh` fallback.
- `action.yml`: the composite GitHub Action wrapping the CLI.

See `docs/architecture/topology.md` for the full tree.

## Docs map

- `README.md` (this file)
- `docs/architecture/topology.md`
- `LICENSE`

## Consumers

None inside the `alawein` hub repo's own CI as of this check (no workflow
file there references `alawein/repo-drift`). It is a standalone
tool/action any repo (in or outside the `alawein` org) can adopt via the
GitHub Action or the CLI.

## Release and versioning

- Version source: `pyproject.toml` (`project.version`).
- Publish mode: manual (tag a release, e.g. `v0.1.0`, after bumping the
  version in `pyproject.toml`); downstream users pin the tag or its
  commit SHA in their workflow's `uses:` line.

## License and attribution

Licensed under the [MIT License](LICENSE).
