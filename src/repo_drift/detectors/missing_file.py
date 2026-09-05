"""Check that required files exist and optionally validate them with local schemas.

``required`` is a list of files, relative to the repository root, that must
exist. ``schemas`` maps a target file to a JSON Schema file, also relative to
the repository root. A schema is applied only when its target file exists.

No schemas are bundled with repo-drift: projects keep their own validation
contract in the repository being checked. This keeps the action generic and
avoids embedding organization-specific operational metadata.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from repo_drift.finding import Finding


def detect(repo_root: Path, config: dict) -> list[Finding]:
    required = list(config.get("required") or [])
    schema_paths = dict(config.get("schemas") or {})

    missing_paths: set[str] = set()
    findings: list[Finding] = []
    for rel in required:
        rel_path = _relative_path(rel, label="required file")
        if not (repo_root / rel_path).exists():
            missing_paths.add(rel_path.as_posix())
            findings.append(
                Finding(
                    detector="missing_file",
                    file=rel_path,
                    line=None,
                    message=f"required file {rel_path.as_posix()} is missing",
                    fix_hint=(
                        f"Create {rel_path.as_posix()} or remove it from "
                        ".drift-rules.yaml `required`"
                    ),
                )
            )

    for target_name, schema_name in schema_paths.items():
        target_path = _relative_path(target_name, label="schema target")
        if target_path.as_posix() in missing_paths:
            continue
        full_target = repo_root / target_path
        if not full_target.is_file():
            continue
        schema_path = repo_root / _relative_path(schema_name, label="schema file")
        if not schema_path.is_file():
            raise ValueError(f"schema file does not exist: {schema_path.relative_to(repo_root)}")
        findings.extend(_validate(full_target, target_path, schema_path))

    return findings


def _relative_path(value: object, *, label: str) -> Path:
    path = Path(str(value))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be relative to the repository root: {value!r}")
    return path


def _validate(target_path: Path, rel_target: Path, schema_path: Path) -> list[Finding]:
    try:
        data = _load_data(target_path)
    except (yaml.YAMLError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [
            Finding(
                detector="missing_file",
                file=rel_target,
                line=None,
                message=f"{rel_target.as_posix()} failed to parse as YAML/JSON: {exc}",
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
                detector="missing_file",
                file=rel_target,
                line=None,
                message=f"{rel_target.as_posix()}: {location}: {error.message}",
                fix_hint=f"Update {rel_target.as_posix()} to match its schema",
            )
        )
    return findings


def _load_data(path: Path) -> object:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)
