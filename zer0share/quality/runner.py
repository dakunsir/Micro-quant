from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from zer0share.quality.models import (
    QualityFinding,
    QualityRunOptions,
    QualityRunReport,
    Severity,
    TableSummary,
)
from zer0share.quality.rules import (
    check_adjustment_factor_values,
    check_duplicate_key,
    check_market_data_values,
    check_required_columns,
)
from zer0share.quality.targets import QualityTarget, get_targets


def _date_range(start_date: str, end_date: str) -> list[str]:
    start = dt.datetime.strptime(start_date, "%Y%m%d").date()
    end = dt.datetime.strptime(end_date, "%Y%m%d").date()
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    days: list[str] = []
    current = start
    while current <= end:
        days.append(current.strftime("%Y%m%d"))
        current += dt.timedelta(days=1)
    return days


def _normalize_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str), errors="coerce").dt.strftime("%Y%m%d")


class QualityRunner:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def run(self, options: QualityRunOptions) -> QualityRunReport:
        targets = get_targets(list(options.tables))
        summaries: list[TableSummary] = []
        findings: list[QualityFinding] = []

        for target in targets:
            summary, target_findings = self._run_target(target, options)
            summaries.append(summary)
            findings.extend(target_findings)

        return QualityRunReport(options=options, summaries=summaries, findings=findings)

    def _run_target(
        self,
        target: QualityTarget,
        options: QualityRunOptions,
    ) -> tuple[TableSummary, list[QualityFinding]]:
        target_dir = self._target_dir(target)
        findings: list[QualityFinding] = []

        if not target_dir.exists():
            findings.append(
                QualityFinding(
                    table=target.table,
                    date=None,
                    severity=Severity.FAIL,
                    rule="table_directory_exists",
                    count=1,
                    message=f"table directory does not exist: {target_dir}",
                )
            )
            return self._summary(target, 0, 0, findings), findings

        expected_dates = self._expected_dates(options)
        rows = 0
        partitions = 0

        for date_value in expected_dates:
            parquet_path = target_dir / f"date={date_value}" / "data.parquet"
            if not parquet_path.exists():
                findings.append(
                    QualityFinding(
                        table=target.table,
                        date=date_value,
                        severity=Severity.WARN,
                        rule="missing_partition",
                        count=1,
                        message=f"missing partition: {parquet_path}",
                    )
                )
                continue

            try:
                df = pd.read_parquet(parquet_path)
            except Exception as exc:  # pragma: no cover - exercised through integration tests
                findings.append(
                    QualityFinding(
                        table=target.table,
                        date=date_value,
                        severity=Severity.FAIL,
                        rule="readable_parquet",
                        count=1,
                        message=f"failed to read parquet: {exc}",
                    )
                )
                continue

            partitions += 1
            rows += len(df)

            if df.empty:
                findings.append(
                    QualityFinding(
                        table=target.table,
                        date=date_value,
                        severity=Severity.WARN,
                        rule="empty_partition",
                        count=1,
                        message="partition contains zero rows",
                    )
                )

            findings.extend(self._check_frame(target, date_value, df))

        return self._summary(target, partitions, rows, findings), findings

    def _target_dir(self, target: QualityTarget) -> Path:
        path = self.data_dir
        for part in target.spec.path_parts:
            path = path / part
        return path

    def _expected_dates(self, options: QualityRunOptions) -> list[str]:
        if options.mode == "full":
            if options.start_date is None or options.end_date is None:
                raise ValueError("full mode requires start_date and end_date")
            return self._trading_dates(options.start_date, options.end_date)

        if options.mode == "daily":
            if options.date is not None:
                return [options.date]
            if options.end_date is not None:
                return [options.end_date]
            if options.start_date is not None:
                return [options.start_date]
            raise ValueError("daily mode requires date, end_date, or start_date")

        raise ValueError(f"unknown quality mode: {options.mode}")

    def _trading_dates(self, start_date: str, end_date: str) -> list[str]:
        trade_cal_dir = self.data_dir / "stock" / "trade_cal"
        parquet_paths = sorted(trade_cal_dir.glob("exchange=*/data.parquet"))
        if not parquet_paths:
            return _date_range(start_date, end_date)

        frames: list[pd.DataFrame] = []
        for parquet_path in parquet_paths:
            try:
                frame = pd.read_parquet(parquet_path)
            except Exception:
                continue
            if not frame.empty:
                frames.append(frame)

        if not frames:
            return _date_range(start_date, end_date)

        cal = pd.concat(frames, ignore_index=True)
        if "cal_date" not in cal.columns or "is_open" not in cal.columns:
            return _date_range(start_date, end_date)

        cal_dates = _normalize_dates(cal["cal_date"])
        is_open = cal["is_open"].fillna(False).astype(bool)
        mask = (
            cal_dates.notna()
            & (cal_dates >= start_date)
            & (cal_dates <= end_date)
            & is_open
        )
        return sorted(set(cal_dates[mask].tolist()))

    def _check_frame(
        self,
        target: QualityTarget,
        date_value: str,
        df: pd.DataFrame,
    ) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        findings.extend(check_required_columns(target.table, date_value, df, list(target.spec.columns)))
        findings.extend(check_duplicate_key(target.table, date_value, df, target.primary_key))
        if target.kind == "market_data":
            findings.extend(check_market_data_values(target.table, date_value, df))
        elif target.kind == "adjustment":
            findings.extend(check_adjustment_factor_values(target.table, date_value, df))
        return findings

    def _summary(
        self,
        target: QualityTarget,
        partitions: int,
        rows: int,
        findings: list[QualityFinding],
    ) -> TableSummary:
        target_findings = [finding for finding in findings if finding.table == target.table]
        warn_count = sum(1 for finding in target_findings if finding.severity == Severity.WARN)
        fail_count = sum(1 for finding in target_findings if finding.severity == Severity.FAIL)
        pass_count = 1 if warn_count == 0 and fail_count == 0 and partitions > 0 else 0
        return TableSummary(
            table=target.table,
            market=target.market,
            partitions=partitions,
            rows=rows,
            pass_count=pass_count,
            warn_count=warn_count,
            fail_count=fail_count,
        )
