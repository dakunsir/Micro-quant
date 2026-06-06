import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

from zer0share.query import QueryContext


@dataclass(frozen=True)
class TableSpec:
    name: str
    path_parts: tuple[str, ...]
    columns: list[str]
    parquet_pattern: str
    sync_table: str
    order_by: str
    hive_partitioning: bool = False
    union_by_name: bool = False


@dataclass(frozen=True)
class DailyTableSpec(TableSpec):
    date_column: str = "trade_date"
    code_column: str | None = "ts_code"


@dataclass(frozen=True)
class SqlFilter:
    clause: str
    params: tuple[object, ...] = ()


def parse_fields(fields, default_columns: list[str]) -> list[str]:
    if fields is None:
        return list(default_columns)
    if isinstance(fields, str):
        parsed = [f.strip() for f in fields.split(",") if f.strip()]
    else:
        parsed = list(fields)
    unknown = [f for f in parsed if f not in default_columns]
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(unknown)}")
    return parsed


def parse_date(value: str):
    try:
        return dt.datetime.strptime(value, "%Y%m%d").date()
    except ValueError as e:
        raise ValueError(f"invalid date format: {value}; expected YYYYMMDD") from e


def _validate_filter_column(column: str, allowed_columns: Iterable[str]) -> None:
    if column not in allowed_columns:
        raise ValueError(f"unknown filter column: {column}")


def eq_filter(column: str, value, allowed_columns: Iterable[str]) -> SqlFilter:
    _validate_filter_column(column, allowed_columns)
    return SqlFilter(f"{column} = ?", (value,))


def in_filter(column: str, values, allowed_columns: Iterable[str]) -> SqlFilter:
    _validate_filter_column(column, allowed_columns)
    items = (
        [item.strip() for item in values.split(",") if item.strip()]
        if isinstance(values, str)
        else list(values)
    )
    placeholders = ", ".join("?" for _ in items)
    return SqlFilter(f"{column} IN ({placeholders})", tuple(items))


def date_range_filters(
    column: str,
    trade_date,
    start_date,
    end_date,
    allowed_columns: Iterable[str],
) -> list[SqlFilter]:
    _validate_filter_column(column, allowed_columns)
    if trade_date is not None and (start_date is not None or end_date is not None):
        raise ValueError("trade_date cannot be combined with start_date or end_date")
    parsed_start = parse_date(start_date) if start_date is not None else None
    parsed_end = parse_date(end_date) if end_date is not None else None
    if parsed_start is not None and parsed_end is not None and parsed_end < parsed_start:
        raise ValueError("end_date must be on or after start_date")

    filters = []
    if trade_date is not None:
        filters.append(SqlFilter(f"{column} = ?", (parse_date(trade_date).strftime("%Y%m%d"),)))
    if parsed_start is not None:
        filters.append(SqlFilter(f"{column} >= ?", (parsed_start.strftime("%Y%m%d"),)))
    if parsed_end is not None:
        filters.append(SqlFilter(f"{column} <= ?", (parsed_end.strftime("%Y%m%d"),)))
    return filters


class ParquetQueryEngine:
    _ORDER_BY_RE = re.compile(
        r"^[\w]+(?:\s+(?:ASC|DESC))?(?:,\s*[\w]+(?:\s+(?:ASC|DESC))?)*$",
        re.IGNORECASE,
    )

    def select(
        self,
        source: Path,
        columns: list[str],
        filters: list[SqlFilter],
        order_by: str,
        limit: int | None = None,
        offset: int | None = None,
        hive_partitioning: bool = False,
        union_by_name: bool = False,
    ) -> pd.DataFrame:
        if not self._ORDER_BY_RE.match(order_by):
            raise ValueError(f"invalid order_by: {order_by!r}")

        options = ["?"]
        if hive_partitioning:
            options.append("hive_partitioning=true")
        if union_by_name:
            options.append("union_by_name=true")

        sql = f"SELECT {', '.join(columns)} FROM read_parquet({', '.join(options)})"
        params: list[object] = [str(source)]
        if filters:
            sql += " WHERE " + " AND ".join(f.clause for f in filters)
            for filt in filters:
                params.extend(filt.params)
        sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            sql += " OFFSET ?"
            params.append(offset)

        return duckdb.connect().execute(sql, params).fetchdf()


class BaseParquetRepository:
    def __init__(
        self,
        ctx: QueryContext,
        spec: TableSpec,
        engine: ParquetQueryEngine | None = None,
    ):
        self.ctx = ctx
        self.spec = spec
        self.engine = engine or ParquetQueryEngine()

    @property
    def table_dir(self) -> Path:
        path = self.ctx.data_dir
        for part in self.spec.path_parts:
            path = path / part
        return path

    @property
    def source(self) -> Path:
        return self.table_dir / self.spec.parquet_pattern

    def ensure_exists(self) -> None:
        if self.table_dir.exists():
            return
        if self.spec.sync_table == "build-universe":
            raise FileNotFoundError(
                "universe data not found; run `python main.py build-universe` first"
            )
        raise FileNotFoundError(
            f"{self.spec.sync_table} data not found; run `python main.py sync --table {self.spec.sync_table}` first"
        )

    def query(
        self,
        fields=None,
        filters: list[SqlFilter] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> pd.DataFrame:
        self.ensure_exists()
        selected = parse_fields(fields, self.spec.columns)
        return self.engine.select(
            source=self.source,
            columns=selected,
            filters=filters or [],
            order_by=order_by or self.spec.order_by,
            limit=limit,
            offset=offset,
            hive_partitioning=self.spec.hive_partitioning,
            union_by_name=self.spec.union_by_name,
        )


class DailyPartitionRepository(BaseParquetRepository):
    spec: DailyTableSpec

    def __init__(
        self,
        ctx: QueryContext,
        spec: DailyTableSpec,
        engine: ParquetQueryEngine | None = None,
    ):
        super().__init__(ctx, spec, engine)

    def query(
        self,
        code=None,
        trade_date=None,
        start_date=None,
        end_date=None,
        fields=None,
        filters: list[SqlFilter] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> pd.DataFrame:
        query_filters = []
        if code is not None:
            if self.spec.code_column is None:
                raise ValueError(f"{self.spec.name} does not support code filtering")
            query_filters.append(in_filter(self.spec.code_column, code, self.spec.columns))
        query_filters.extend(
            date_range_filters(
                self.spec.date_column,
                trade_date,
                start_date,
                end_date,
                self.spec.columns,
            )
        )
        if filters:
            query_filters.extend(filters)
        return super().query(
            fields=fields,
            filters=query_filters,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
