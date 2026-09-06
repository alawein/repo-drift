# Topology

Actual tree, not aspirational. Regenerate this by hand when `src/` changes shape.

```text
repo-drift/
├── action.yml                  # composite GitHub Action wrapping the CLI
├── pyproject.toml              # package metadata, version source
├── src/
│   └── repo_drift/
│       ├── __main__.py         # `python -m repo_drift`
│       ├── cli.py              # `repo-drift check` / `repo-drift explain`
│       ├── runner.py           # loads rules, runs detectors
│       ├── rules.py            # .drift-rules.yaml parsing
│       ├── registry.py         # detector name -> implementation
│       ├── finding.py          # detector result type
│       ├── reporters.py        # text / GitHub Actions annotation output
│       ├── _github.py          # optional gh-backed metadata lookups
│       └── detectors/
│           ├── branch_name.py
│           ├── claimed_dep.py
│           ├── feature_claim.py
│           ├── missing_file.py
│           ├── stale_config.py
│           └── visibility.py
└── tests/
    ├── test_action.py
    ├── test_cli_and_reporters.py
    └── test_detectors.py
```

## Boundaries

- `cli.py` / `__main__.py` are the only entry points; everything else is a
  library import, so the CLI stays thin.
- `runner.py` and `rules.py` own configuration; they never call a detector
  directly by name, only through `registry.py`.
- `detectors/*` are independent: each reads the target directory and the
  rule config for its own key, returns `Finding` objects, and has no
  import of another detector.
- `_github.py` is the sole network boundary. Only `branch_name` and
  `visibility` call into it, and only as an optional fallback.
