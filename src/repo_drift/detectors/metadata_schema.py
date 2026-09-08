"""metadata_schema — validate `service-metadata.yaml` against a local JSON Schema.

Configuration (opt-in: no-op unless `schema` is present):
  schema — required to enable the detector. Path to a JSON Schema file,
           relative to the repository root.
  target — optional path, defaults to "service-metadata.yaml".

No schema is bundled with repo-drift; each repo keeps its own schema
reference in `.drift-rules.yaml`, matching the pattern in `missing_file.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from repo_drift.finding import Finding


def detect(repo_root: Path, config: dict) -> list[Finding]:
    schema_rel = config.get("schema")
    if not schema_rel:
        return []

    target_rel = config.get("target", "service-metadata.yaml")
    target_path = repo_root / target_rel
    rel_target = Path(target_rel)

    if not target_path.is_file():
        return [
            Finding(
                detector="metadata_schema",
                file=rel_target,
                line=None,
                message=f"{rel_target.as_posix()} is missing",
                fix_hint="Render service-metadata.yaml from the kernel or author it manually",
            )
        ]

    schema_path = repo_root / schema_rel
    if not schema_path.is_file():
        raise ValueError(f"schema file does not exist: {schema_path.relative_to(repo_root)}")

    try:
        data = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        return [
            Finding(
                detector="metadata_schema",
                file=rel_target,
                line=None,
                message=f"{rel_target.as_posix()} failed to parse as YAML: {exc}",
                fix_hint="Fix the syntax error in the file",
            )
        ]

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid JSON Schema at {schema_path}: {exc}") from exc

    validator = Draft202012Validator(schema)
    findings: list[Finding] = []
    for error in validator.iter_errors(data):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        findings.append(
            Finding(
                detector="metadata_schema",
                file=rel_target,
                line=None,
                message=f"{rel_target.as_posix()}: {location}: {error.message}",
                fix_hint=f"Update {rel_target.as_posix()} to match its schema",
            )
        )
    return findings
