"""claimed_dep — flag tracked packages mentioned in docs but absent from manifests.

Reads docs (README.md, CLAUDE.md, AGENTS.md, SSOT.md by default) and looks for
references to a curated list of SDK packages. For every reference, requires
the package to appear in package.json (any of dependencies / devDependencies /
peerDependencies / optionalDependencies) or pyproject.toml (project
dependencies, optional-dependencies, or poetry dependencies).

A documented disclaimer ("key storage only, no live SDK …") near the mention
suppresses the finding so legitimate "we don't ship the SDK" docs don't fail
the build.

Word-boundary matching is intentional and conservative: we don't want
`openai-client` or a path fragment like `vendor/openai/x` to trip a finding
for `openai`.

Configuration (via .drift-rules.yaml `detector_config.claimed_dep`):
  tracked_packages.js  — list of npm package names to track
  tracked_packages.py  — list of pypi package names to track
  claims_files         — doc files to scan
  disclaimer_pattern   — regex; presence within window suppresses
  disclaimer_window    — lines before/after the claim to scan for disclaimer
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable
from pathlib import Path

from repo_drift.finding import Finding

DEFAULT_TRACKED_PACKAGES: dict[str, list[str]] = {
    "js": [
        "@huggingface/transformers",
        "@capacitor/core",
        "@capacitor/cli",
        "@anthropic-ai/sdk",
        "@google/generative-ai",
        "openai",
        "anthropic",
        "cohere-ai",
        "ollama",
    ],
    "py": [
        "anthropic",
        "openai",
        "transformers",
        "huggingface-hub",
        "huggingface_hub",
        "langchain",
        "cohere",
    ],
}

DEFAULT_CLAIMS_FILES = ("README.md", "CLAUDE.md", "AGENTS.md", "SSOT.md")
DEFAULT_DISCLAIMER_PATTERN = r"key\s*storage only|no live SDK|placeholder integration"
DEFAULT_DISCLAIMER_WINDOW = 5

_NPM_MANIFEST = "package.json"
_PY_MANIFEST = "pyproject.toml"
_NPM_DEP_KEYS = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)
_PEP_SPEC_SPLIT = re.compile(r"[<>=!~\[;\s]")


def detect(repo_root: Path, config: dict) -> list[Finding]:
    tracked = config.get("tracked_packages") or DEFAULT_TRACKED_PACKAGES
    claims_files = tuple(config.get("claims_files") or DEFAULT_CLAIMS_FILES)
    disclaimer_pattern = config.get("disclaimer_pattern", DEFAULT_DISCLAIMER_PATTERN)
    disclaimer_window = int(config.get("disclaimer_window", DEFAULT_DISCLAIMER_WINDOW))

    js_present = _read_npm_deps(repo_root / _NPM_MANIFEST)
    py_present = _read_pyproject_deps(repo_root / _PY_MANIFEST)

    findings: list[Finding] = []
    for ecosystem, packages in (
        ("js", tracked.get("js") or []),
        ("py", tracked.get("py") or []),
    ):
        present = js_present if ecosystem == "js" else py_present
        if present is None:
            continue  # manifest absent — nothing to compare against
        findings.extend(
            _scan(
                repo_root=repo_root,
                ecosystem=ecosystem,
                packages=packages,
                present=present,
                claims_files=claims_files,
                disclaimer_pattern=disclaimer_pattern,
                disclaimer_window=disclaimer_window,
            )
        )
    return findings


def _scan(
    *,
    repo_root: Path,
    ecosystem: str,
    packages: Iterable[str],
    present: set[str],
    claims_files: tuple[str, ...],
    disclaimer_pattern: str,
    disclaimer_window: int,
) -> list[Finding]:
    findings: list[Finding] = []
    pattern_re = re.compile(disclaimer_pattern, re.IGNORECASE) if disclaimer_pattern else None
    install_verb = "npm install" if ecosystem == "js" else "pip install"
    present_lower = {p.lower() for p in present}

    for claim_file in claims_files:
        doc_path = repo_root / claim_file
        if not doc_path.is_file():
            continue
        text = doc_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for pkg in packages:
            if pkg.lower() in present_lower:
                continue
            pkg_re = _package_match_regex(pkg)
            for lineno, line in enumerate(lines, start=1):
                if not pkg_re.search(line):
                    continue
                if pattern_re and _disclaimer_nearby(lines, lineno, pattern_re, disclaimer_window):
                    continue
                findings.append(
                    Finding(
                        detector="claimed_dep",
                        file=Path(claim_file),
                        line=lineno,
                        message=(
                            f"{pkg} referenced in {claim_file} but absent from "
                            f"{_NPM_MANIFEST if ecosystem == 'js' else _PY_MANIFEST}"
                        ),
                        fix_hint=(f"Remove the {pkg} reference or `{install_verb} {pkg}`"),
                    )
                )
    return findings


def _package_match_regex(pkg: str) -> re.Pattern[str]:
    # Case-insensitive because brand names are routinely written in title case
    # in prose ("OpenAI", "Anthropic") even when the npm package id is lowercase.
    # Negative-class word boundaries keep us from matching openai-client or
    # path fragments like vendor/openai/x. Forward slash is in the boundary
    # class so `path/openai` doesn't match either; the package name's own
    # internal `/` (e.g. `@scope/name`) still matches because it's part of the
    # literal escaped pattern.
    return re.compile(
        r"(?<![A-Za-z0-9_/\-@])" + re.escape(pkg) + r"(?![A-Za-z0-9_/\-]|\.[A-Za-z0-9_-])",
        re.IGNORECASE,
    )


def _disclaimer_nearby(
    lines: list[str],
    lineno: int,
    pattern: re.Pattern[str],
    window: int,
) -> bool:
    start = max(0, lineno - 1 - window)
    end = min(len(lines), lineno - 1 + window + 1)
    return any(pattern.search(line) for line in lines[start:end])


def _read_npm_deps(path: Path) -> set[str] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    deps: set[str] = set()
    for key in _NPM_DEP_KEYS:
        section = data.get(key) or {}
        if isinstance(section, dict):
            deps.update(section.keys())
    return deps


def _read_pyproject_deps(path: Path) -> set[str] | None:
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return set()

    deps: set[str] = set()
    project = data.get("project") or {}
    for spec in project.get("dependencies") or []:
        deps.add(_pep_spec_to_name(spec))
    for group in (project.get("optional-dependencies") or {}).values():
        for spec in group or []:
            deps.add(_pep_spec_to_name(spec))

    poetry = (data.get("tool") or {}).get("poetry") or {}
    deps.update((poetry.get("dependencies") or {}).keys())
    deps.update((poetry.get("dev-dependencies") or {}).keys())
    return deps


def _pep_spec_to_name(spec: str) -> str:
    return _PEP_SPEC_SPLIT.split(spec, maxsplit=1)[0].strip()
