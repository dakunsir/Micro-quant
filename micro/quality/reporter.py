from __future__ import annotations

import csv
import datetime as dt
import json
import subprocess
from pathlib import Path

from micro.quality.models import QualityRunReport


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def format_summary(report: QualityRunReport) -> str:
    lines = [
        (
            "quality report: "
            f"mode={report.options.mode} "
            f"tables={len(report.options.tables)} "
            f"findings={len(report.findings)} "
            f"fail={report.fail_count} "
            f"warn={report.warn_count}"
        )
    ]

    for summary in report.summaries:
        row = summary.to_row()
        lines.append(
            " | ".join(
                [
                    str(row["table"]),
                    f"market={row['market']}",
                    f"partitions={row['partitions']}",
                    f"rows={row['rows']}",
                    f"pass={row['pass']}",
                    f"warn={row['warn']}",
                    f"fail={row['fail']}",
                ]
            )
        )

    return "\n".join(lines)


class QualityReporter:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def write(self, report: QualityRunReport) -> Path:
        output_dir = self.base_dir / _timestamp()
        output_dir.mkdir(parents=True, exist_ok=False)

        self._write_csv(
            output_dir / "summary.csv",
            [summary.to_row() for summary in report.summaries],
            ["table", "market", "partitions", "rows", "pass", "warn", "fail"],
        )
        self._write_csv(
            output_dir / "findings.csv",
            [finding.to_row() for finding in report.findings],
            ["table", "date", "severity", "rule", "count", "message", "sample"],
        )

        metadata = {
            "mode": report.options.mode,
            "tables": list(report.options.tables),
            "start_date": report.options.start_date,
            "end_date": report.options.end_date,
            "date": report.options.date,
            "git_commit": _git_commit(),
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_dir

    def _write_csv(
        self,
        path: Path,
        rows: list[dict[str, object]],
        fieldnames: list[str],
    ) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
