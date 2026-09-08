# repo-drift

## The claim

Catches a repo's documentation and config drifting away from what it
actually claims: a stale default branch name in the docs, a dependency
named in prose but missing from the manifest, a visibility mismatch, a
required file that went missing. Consumed as a GitHub Action in CI or as
a standalone CLI for a local check.

### Status

Preview-only. This repository has no automated CI. Run the development checks
below before relying on a new revision.

## Run it

Requires Python 3.11+ and Git. Install from the pinned source revision below.
The PyPI package named `repo-drift` belongs to a different project.

```bash
python -m pip install "repo-drift @ git+https://github.com/alawein/repo-drift.git@d0ba158fa9188298f57e81c2a2260398a50d5b40"
repo-drift explain
```

Or pin the GitHub Action (see below) without installing anything locally.

## What it is

A configurable Python CLI and GitHub Action for repository maintainers.
With `--reporter github`, it emits workflow commands that render findings as
inline annotations.

## What it is not

It has no credential store, network SDK, telemetry, or private package dependency.
The `visibility` and `branch_name` checks can invoke the locally authenticated
`gh` command when their rules require metadata; failures become warnings.

## Purpose

Check declared repository rules before publishing documentation or merging a
pull request.

## Install

Use [Run it](#run-it) for a local installation, or the GitHub Action below.

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
repo-drift check --reporter github
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
- `kernel_conformance`: compares `.kernel-manifest.json` against an expected
  kernel version and file-hash map. Opt-in: no-op unless
  `expected_kernel_version` and `expected_files` are configured.
- `workflow_pin`: flags reusable-workflow `uses:` references in
  `.github/workflows/*.yml` that don't match a single pinned SHA. Opt-in:
  no-op unless `expected_sha` is configured.
- `agent_contract`: checks `AGENTS.md` for required managed sections.
  Opt-in: no-op unless `required_sections` is configured.
- `metadata_schema`: validates `service-metadata.yaml` (or another target)
  against a local JSON Schema. Opt-in: no-op unless `schema` is configured.
- `worktree_registry`: local-only; warns when `git worktree list` reports a
  worktree outside the configured registered roots. Opt-in: no-op unless
  `registered_roots` is configured.

`schemas` deliberately points to JSON Schema files in the repository being
checked; repo-drift includes no organization-specific metadata schema.
JSON Schema validation may retrieve remote `$ref` targets. The five
kernel-canonicalization detectors above follow the same "opt-in via
required config keys" convention as `visibility`: they are always
registered, but stay silent until a repo's `.drift-rules.yaml`
`detector_config` supplies their required keys, so adoption happens per
wave rather than fleet-wide on upgrade.

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
  `visibility`, `kernel_conformance`, `workflow_pin`, `agent_contract`,
  `metadata_schema`, `worktree_registry`); see `registry.py` for how they're
  wired up.
- `src/repo_drift/reporters.py`, `finding.py`: turn detector results into
  plain-text or GitHub Actions annotation output.
- `src/repo_drift/_github.py`: optional GitHub metadata lookups used by the
  `visibility` and `branch_name` detectors.
- `action.yml`: the composite GitHub Action wrapping the CLI.

See `docs/architecture/topology.md` for the full tree.

## Docs map

- [README.md](README.md) (this file)
- [Architecture topology](docs/architecture/topology.md)
- [License](LICENSE)

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

## License

Licensed under the [MIT License](LICENSE).
