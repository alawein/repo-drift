"""feature_claim — flag README features that have no source-code backing.

Operator declares feature claims in .drift-rules.yaml. Each claim is a list of
tokens; if NONE of the tokens appears in any source file under src_dirs, the
detector emits a finding for every doc location that references one of the
tokens.

Empty / missing config is intentionally a no-op so registering this detector
globally is safe — it only acts when an operator opts in.

Configuration (via .drift-rules.yaml `detector_config.feature_claim`):
  src_dirs        — directories to grep for token matches (default: ["src"])
  claims          — list of {tokens, in_files?, description?}
    tokens        — list of strings; ANY token finding in src suppresses
    in_files      — doc files to scan; default README.md + CLAUDE.md
    description   — included verbatim in finding message; defaults to tokens

Token matching is case-insensitive with regex word boundaries so
`evaluation` does not satisfy a claim of `eval`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from repo_drift.finding import Finding

DEFAULT_SRC_DIRS = ("src",)
DEFAULT_IN_FILES = ("README.md", "CLAUDE.md")
_SRC_FILE_EXTENSIONS = (
    ".py",
    ".pyx",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".go",
    ".rs",
    ".rb",
    ".java",
    ".kt",
    ".scala",
    ".swift",
    ".m",
    ".mm",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".php",
    ".lua",
    ".sh",
    ".sql",
    ".graphql",
)
# Skip vendored / generated / VCS directories. A vendored copy of a token
# in node_modules must not silently satisfy a feature claim, and a
# misconfigured `src_dirs: ["."]` must not walk the entire repo.
_EXCLUDED_DIR_NAMES = frozenset(
    {
        "node_modules",
        ".git",
        ".hg",
        ".svn",
        "dist",
        "build",
        ".next",
        ".nuxt",
        ".turbo",
        ".cache",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        "target",  # rust / java
    }
)


def detect(repo_root: Path, config: dict) -> list[Finding]:
    claims = config.get("claims") or []
    if not claims:
        return []

    src_dirs = tuple(config.get("src_dirs") or DEFAULT_SRC_DIRS)
    src_files = _collect_src_files(repo_root, src_dirs)

    findings: list[Finding] = []
    for claim in claims:
        findings.extend(_evaluate_claim(repo_root, claim, src_dirs, src_files))
    return findings


def _evaluate_claim(
    repo_root: Path,
    claim: dict,
    src_dirs: tuple[str, ...],
    src_files: list[Path],
) -> list[Finding]:
    tokens = list(claim.get("tokens") or [])
    if not tokens:
        return []

    in_files = tuple(claim.get("in_files") or DEFAULT_IN_FILES)
    description = claim.get("description") or " | ".join(tokens)

    token_patterns = [_token_regex(t) for t in tokens]
    if _any_token_in_src(token_patterns, src_files):
        return []

    findings: list[Finding] = []
    for in_file in in_files:
        doc_path = repo_root / in_file
        if not doc_path.is_file():
            continue
        text = doc_path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(p.search(line) for p in token_patterns):
                findings.append(
                    Finding(
                        detector="feature_claim",
                        file=Path(in_file),
                        line=lineno,
                        message=(
                            f"{description} claimed in {in_file} but no matches in {list(src_dirs)}"
                        ),
                        fix_hint=(
                            f"Add an implementation under {src_dirs[0]}/ or remove the claim"
                        ),
                    )
                )
    return findings


def _token_regex(token: str) -> re.Pattern[str]:
    # Explicit boundary class instead of \b: Python's \b treats underscore as a
    # word character, so `\badversarial\b` would not match `test_adversarial_input`.
    # Using [A-Za-z0-9] lets snake_case and CONST_CASE identifiers count as matches.
    return re.compile(
        r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def _any_token_in_src(
    patterns: list[re.Pattern[str]],
    src_files: Iterable[Path],
) -> bool:
    for path in src_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(p.search(text) for p in patterns):
            return True
    return False


def _collect_src_files(repo_root: Path, src_dirs: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for src_dir in src_dirs:
        root = repo_root / src_dir
        if not root.is_dir():
            continue
        for ext in _SRC_FILE_EXTENSIONS:
            for path in root.rglob(f"*{ext}"):
                if any(part in _EXCLUDED_DIR_NAMES for part in path.parts):
                    continue
                files.append(path)
    return files
