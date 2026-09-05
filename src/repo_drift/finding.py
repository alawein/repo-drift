"""Finding dataclass — the unit of detector output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ALLOWED_SEVERITIES = frozenset({"error", "warning", "info"})


@dataclass(frozen=True)
class Finding:
    detector: str
    file: Path
    line: int | None
    message: str
    fix_hint: str | None = None
    severity: str = "error"

    def __post_init__(self) -> None:
        if self.severity not in _ALLOWED_SEVERITIES:
            raise ValueError(
                f"severity must be one of {sorted(_ALLOWED_SEVERITIES)}, got {self.severity!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "file": str(self.file).replace("\\", "/"),
            "line": self.line,
            "message": self.message,
            "fix_hint": self.fix_hint,
            "severity": self.severity,
        }
