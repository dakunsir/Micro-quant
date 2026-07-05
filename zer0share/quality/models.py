from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class QualityFinding:
    table: str
    date: str | None
    severity: Severity
    rule: str
    count: int
    message: str
    sample: list[dict[str, object]] = field(default_factory=list)

    def to_row(self) -> dict[str, object]:
        return {
            "table": self.table,
            "date": self.date or "",
            "severity": self.severity.value,
            "rule": self.rule,
            "count": self.count,
            "message": self.message,
            "sample": json.dumps(self.sample, ensure_ascii=False, default=str),
        }


@dataclass(frozen=True)
class TableSummary:
    table: str
    market: str
    partitions: int
    rows: int
    pass_count: int
    warn_count: int
    fail_count: int

    def to_row(self) -> dict[str, object]:
        return {
            "table": self.table,
            "market": self.market,
            "partitions": self.partitions,
            "rows": self.rows,
            "pass": self.pass_count,
            "warn": self.warn_count,
            "fail": self.fail_count,
        }


@dataclass(frozen=True)
class QualityRunOptions:
    mode: str
    tables: tuple[str, ...]
    start_date: str | None = None
    end_date: str | None = None
    date: str | None = None
    report_dir: Path | None = None


@dataclass(frozen=True)
class QualityRunReport:
    options: QualityRunOptions
    summaries: list[TableSummary]
    findings: list[QualityFinding]
    output_dir: Path | None = None

    @property
    def fail_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == Severity.FAIL)

    @property
    def warn_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == Severity.WARN)
