# Query Module OO Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `zer0share.query` to use an object-oriented Parquet query layer while preserving the existing `LocalPro` API and query behavior.

**Architecture:** Add small reusable query infrastructure around `TableSpec`, `SqlFilter`, `ParquetQueryEngine`, `BaseParquetRepository`, and `DailyPartitionRepository`. Keep public domain functions explicit and migrate them to repositories in stages, so existing tests verify behavior preservation after each step.

**Tech Stack:** Python 3.11, DuckDB, Pandas, PyArrow, pytest, uv.

---

## File Structure

- Create `zer0share/query/repository.py`: table metadata, safe SQL filters, DuckDB query engine, base repository, daily partition repository.
- Modify `zer0share/query/_helpers.py`: keep parse helpers; make `query_daily_partitioned()` delegate to `DailyPartitionRepository`; fix the current stray `I` syntax issue.
- Modify `zer0share/query/equities.py`: use `BaseParquetRepository` for `stock_basic`, `index_weight`, and `universe`; leave `pro_bar` logic unchanged.
- Modify `zer0share/query/calendar.py`: use repository infrastructure for `trade_cal`.
- Modify `zer0share/query/futures.py`: use `BaseParquetRepository` for `fut_basic`; keep daily futures wrappers on `query_daily_partitioned()`.
- Modify `zer0share/query/options.py`: use `BaseParquetRepository` for `opt_basic`; keep `opt_daily` on `query_daily_partitioned()`.
- Modify `zer0share/query/industry.py`: use `BaseParquetRepository` for the three industry table queries.
- Create `tests/test_query_repository.py`: focused tests for new repository primitives that are not directly covered by `tests/test_api.py`.
- Modify `tests/test_api.py` only if behavior-preserving tests need a narrow assertion for an uncovered migrated path.

## Task 1: Core Repository Infrastructure

**Files:**
- Create: `zer0share/query/repository.py`
- Test: `tests/test_query_repository.py`

- [ ] **Step 1: Write focused repository tests**

Create `tests/test_query_repository.py` with:

```python
import pandas as pd
import pytest

from zer0share.query import QueryContext
from zer0share.query.repository import (
    BaseParquetRepository,
    DailyPartitionRepository,
    ParquetQueryEngine,
    SqlFilter,
    TableSpec,
    eq_filter,
    in_filter,
)


def test_eq_filter_rejects_unknown_column():
    with pytest.raises(ValueError, match="unknown filter column: not_a_column"):
        eq_filter("not_a_column", "x", ["ts_code"])


def test_in_filter_builds_bound_placeholders():
    filt = in_filter("ts_code", ["000001.SZ", "000002.SZ"], ["ts_code"])

    assert filt.clause == "ts_code IN (?, ?)"
    assert filt.params == ("000001.SZ", "000002.SZ")


def test_engine_rejects_invalid_order_by(tmp_path):
    path = tmp_path / "data.parquet"
    pd.DataFrame({"ts_code": ["000001.SZ"]}).to_parquet(path)

    engine = ParquetQueryEngine()

    with pytest.raises(ValueError, match="invalid order_by"):
        engine.select(
            source=path,
            columns=["ts_code"],
            filters=[],
            order_by="ts_code; DROP TABLE x",
        )


def test_base_repository_queries_static_parquet(tmp_path):
    (tmp_path / "basic").mkdir()
    pd.DataFrame(
        {
            "ts_code": ["000002.SZ", "000001.SZ"],
            "name": ["B", "A"],
        }
    ).to_parquet(tmp_path / "basic" / "data.parquet")

    repo = BaseParquetRepository(
        QueryContext(tmp_path),
        TableSpec(
            name="basic",
            path_parts=("basic",),
            columns=["ts_code", "name"],
            parquet_pattern="data.parquet",
            sync_table="basic",
            order_by="ts_code",
        ),
        ParquetQueryEngine(),
    )

    result = repo.query(fields="ts_code", filters=[eq_filter("name", "A", ["ts_code", "name"])])

    assert result.to_dict("records") == [{"ts_code": "000001.SZ"}]


def test_daily_partition_repository_rejects_trade_date_with_range(tmp_path):
    (tmp_path / "daily_kline").mkdir()
    repo = DailyPartitionRepository(
        QueryContext(tmp_path),
        TableSpec(
            name="daily_kline",
            path_parts=("daily_kline",),
            columns=["ts_code", "trade_date"],
            parquet_pattern="date=*/data.parquet",
            sync_table="daily_kline",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
        ParquetQueryEngine(),
    )

    with pytest.raises(ValueError, match="trade_date cannot be combined"):
        repo.query_by_date(trade_date="20240102", start_date="20240101")


def test_daily_partition_repository_queries_by_date_range(tmp_path):
    day1 = tmp_path / "daily_kline" / "date=20240101"
    day2 = tmp_path / "daily_kline" / "date=20240102"
    day1.mkdir(parents=True)
    day2.mkdir(parents=True)
    pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20240101"], "close": [10.0]}).to_parquet(day1 / "data.parquet")
    pd.DataFrame({"ts_code": ["000002.SZ"], "trade_date": ["20240102"], "close": [20.0]}).to_parquet(day2 / "data.parquet")

    repo = DailyPartitionRepository(
        QueryContext(tmp_path),
        TableSpec(
            name="daily_kline",
            path_parts=("daily_kline",),
            columns=["ts_code", "trade_date", "close"],
            parquet_pattern="date=*/data.parquet",
            sync_table="daily_kline",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
        ParquetQueryEngine(),
    )

    result = repo.query_by_date(start_date="20240102", end_date="20240102", fields="ts_code,close")

    assert result.to_dict("records") == [{"ts_code": "000002.SZ", "close": 20.0}]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_query_repository.py -q
```

Expected: fail because `zer0share.query.repository` does not exist.

- [ ] **Step 3: Implement repository infrastructure**

Create `zer0share/query/repository.py` with:

```python
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
    items = [item.strip() for item in values.split(",") if item.strip()] if isinstance(values, str) else list(values)
    placeholders = ", ".join("?" for _ in items)
    return SqlFilter(f"{column} IN ({placeholders})", tuple(items))


def date_range_filters(column: str, trade_date, start_date, end_date, allowed_columns: Iterable[str]) -> list[SqlFilter]:
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
    def __init__(self, ctx: QueryContext, spec: TableSpec, engine: ParquetQueryEngine | None = None):
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
        if not self.table_dir.exists():
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
    def query_by_date(
        self,
        ts_code=None,
        trade_date=None,
        start_date=None,
        end_date=None,
        fields=None,
        extra_filters: list[SqlFilter] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> pd.DataFrame:
        filters = []
        if ts_code is not None:
            filters.append(in_filter("ts_code", ts_code, self.spec.columns))
        filters.extend(date_range_filters("trade_date", trade_date, start_date, end_date, self.spec.columns))
        if extra_filters:
            filters.extend(extra_filters)
        return self.query(fields=fields, filters=filters, order_by=order_by, limit=limit, offset=offset)
```

- [ ] **Step 4: Run repository tests to verify they pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_query_repository.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit core infrastructure**

Run:

```bash
git add zer0share/query/repository.py tests/test_query_repository.py
git commit -m "refactor: add parquet query repository layer"
```

Expected: commit succeeds with only the new repository and test files.

## Task 2: Delegate Daily Partition Helper

**Files:**
- Modify: `zer0share/query/_helpers.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Replace duplicated daily query SQL with repository delegation**

Update `zer0share/query/_helpers.py` so it imports the shared helpers and delegates `query_daily_partitioned()`:

```python
from pathlib import Path

import pandas as pd

from zer0share.query import QueryContext
from zer0share.query.repository import (
    DailyPartitionRepository,
    ParquetQueryEngine,
    SqlFilter,
    TableSpec,
    eq_filter,
    parse_date,
    parse_fields,
)
```

Keep `parse_is_open()` and `format_date_columns()` in `_helpers.py`. Replace `query_daily_partitioned()` body with:

```python
def query_daily_partitioned(
    ctx: QueryContext,
    table_name: str,
    sync_table: str,
    columns: list[str],
    ts_code,
    trade_date,
    start_date,
    end_date,
    fields,
    extra_filters: dict | None = None,
    data_dir_override: Path | None = None,
    order_by: str = "ts_code, trade_date",
    limit: int | None = None,
    offset: int | None = None,
) -> pd.DataFrame:
    base_ctx = QueryContext(data_dir_override or ctx.data_dir)
    filters: list[SqlFilter] = []
    if extra_filters is not None:
        for col, val in extra_filters.items():
            filters.append(eq_filter(col, val, columns))

    repo = DailyPartitionRepository(
        base_ctx,
        TableSpec(
            name=table_name,
            path_parts=(table_name,),
            columns=columns,
            parquet_pattern="date=*/data.parquet",
            sync_table=sync_table,
            order_by=order_by,
            hive_partitioning=True,
            union_by_name=True,
        ),
        ParquetQueryEngine(),
    )
    return repo.query_by_date(
        ts_code=ts_code,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        extra_filters=filters or None,
        limit=limit,
        offset=offset,
    )
```

This also removes the current stray `I` syntax issue because the old `pattern = ...` line is deleted.

- [ ] **Step 2: Run targeted daily API tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_api.py::test_daily_filters_multiple_codes_by_date_range_and_formats_dates tests/test_api.py::test_daily_rejects_ambiguous_trade_date_and_range tests/test_api.py::test_opt_daily_supports_limit_and_offset tests/test_api.py::test_fut_daily_query_returns_data -q
```

Expected: all tests pass.

- [ ] **Step 3: Run repository tests again**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_query_repository.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit daily helper delegation**

Run:

```bash
git add zer0share/query/_helpers.py
git commit -m "refactor: delegate daily partition queries to repository"
```

Expected: commit succeeds with `_helpers.py`.

## Task 3: Refactor Static Table Queries

**Files:**
- Modify: `zer0share/query/equities.py`
- Modify: `zer0share/query/options.py`
- Modify: `zer0share/query/industry.py`
- Modify: `zer0share/query/futures.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Refactor `stock_basic`**

In `zer0share/query/equities.py`, import repository helpers:

```python
from zer0share.query.repository import BaseParquetRepository, TableSpec, eq_filter, in_filter
```

Replace the body of `stock_basic()` with:

```python
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="basic",
            path_parts=("basic",),
            columns=BASIC_COLS,
            parquet_pattern="data.parquet",
            sync_table="basic",
            order_by="ts_code",
        ),
    )
    filters = []
    if ts_code is not None:
        filters.append(eq_filter("ts_code", ts_code, BASIC_COLS))
    if name is not None:
        filters.append(eq_filter("name", name, BASIC_COLS))
    if market is not None:
        filters.append(eq_filter("market", market, BASIC_COLS))
    if list_status is not None:
        filters.append(eq_filter("list_status", list_status, BASIC_COLS))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, BASIC_COLS))
    if is_hs is not None:
        filters.append(eq_filter("is_hs", is_hs, BASIC_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
```

- [ ] **Step 2: Refactor `opt_basic`**

In `zer0share/query/options.py`, import repository helpers:

```python
from zer0share.query.repository import BaseParquetRepository, TableSpec, eq_filter, in_filter
```

Replace the manual SQL body of `opt_basic()` with:

```python
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="opt_basic",
            path_parts=("options", "opt_basic"),
            columns=OPT_BASIC_COLS,
            parquet_pattern="data.parquet",
            sync_table="opt_basic",
            order_by="ts_code",
        ),
    )
    filters = []
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, OPT_BASIC_COLS))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, OPT_BASIC_COLS))
    if opt_code is not None:
        filters.append(eq_filter("opt_code", opt_code, OPT_BASIC_COLS))
    if call_put is not None:
        filters.append(eq_filter("call_put", call_put, OPT_BASIC_COLS))
    if name is not None:
        filters.append(eq_filter("name", name, OPT_BASIC_COLS))
    if list_date is not None:
        filters.append(eq_filter("list_date", list_date, OPT_BASIC_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
```

- [ ] **Step 3: Refactor industry static queries**

In `zer0share/query/industry.py`, import repository helpers:

```python
from zer0share.query.repository import BaseParquetRepository, TableSpec, eq_filter, in_filter
```

Replace each function body as follows.

`index_classify()`:

```python
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="sw_classify",
            path_parts=("industry", "sw_classify"),
            columns=SW_CLASSIFY_COLS,
            parquet_pattern="data.parquet",
            sync_table="industry",
            order_by="industry_code",
        ),
    )
    filters = []
    if level is not None:
        filters.append(eq_filter("level", level, SW_CLASSIFY_COLS))
    if src is not None:
        filters.append(eq_filter("src", src, SW_CLASSIFY_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
```

`index_member_all()`:

```python
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="sw_member",
            path_parts=("industry", "sw_member"),
            columns=SW_MEMBER_COLS,
            parquet_pattern="data.parquet",
            sync_table="industry",
            order_by="ts_code, l1_code",
        ),
    )
    filters = []
    if l1_code is not None:
        filters.append(eq_filter("l1_code", l1_code, SW_MEMBER_COLS))
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, SW_MEMBER_COLS))
    if is_new is not None:
        filters.append(eq_filter("is_new", is_new, SW_MEMBER_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
```

`ci_index_member()`:

```python
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="ci_member",
            path_parts=("industry", "ci_member"),
            columns=CI_MEMBER_COLS,
            parquet_pattern="data.parquet",
            sync_table="ci_member",
            order_by="ts_code, l1_code",
        ),
    )
    filters = []
    if l1_code is not None:
        filters.append(eq_filter("l1_code", l1_code, CI_MEMBER_COLS))
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, CI_MEMBER_COLS))
    if is_new is not None:
        filters.append(eq_filter("is_new", is_new, CI_MEMBER_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
```

- [ ] **Step 4: Refactor `fut_basic`**

In `zer0share/query/futures.py`, import repository helpers:

```python
from zer0share.query.repository import BaseParquetRepository, TableSpec, eq_filter, in_filter
```

Replace the body of `fut_basic()` with:

```python
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="fut_basic",
            path_parts=("futures", "fut_basic"),
            columns=FUT_BASIC_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_basic",
            order_by="ts_code",
            hive_partitioning=True,
            union_by_name=True,
        ),
    )
    filters = []
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, FUT_BASIC_COLS))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, FUT_BASIC_COLS))
    if fut_code is not None:
        filters.append(eq_filter("fut_code", fut_code, FUT_BASIC_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
```

Preserve the current behavior that `fut_type` is accepted but not filtered.

- [ ] **Step 5: Run static table API tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_api.py::test_stock_basic_filters_and_formats_dates tests/test_api.py::test_opt_basic_query_returns_data tests/test_api.py::test_opt_basic_filters_by_name_and_list_date tests/test_api.py::test_opt_basic_supports_limit_and_offset tests/test_api.py::test_fut_basic_query_returns_data tests/test_api.py::test_fut_basic_query_filters_by_exchange -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Run full API tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_api.py -q
```

Expected: all API tests pass.

- [ ] **Step 7: Commit static table refactor**

Run:

```bash
git add zer0share/query/equities.py zer0share/query/options.py zer0share/query/industry.py zer0share/query/futures.py
git commit -m "refactor: use repositories for static query tables"
```

Expected: commit succeeds with the four domain modules.

## Task 4: Refactor Date-Special Queries

**Files:**
- Modify: `zer0share/query/calendar.py`
- Modify: `zer0share/query/equities.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Refactor `trade_cal`**

In `zer0share/query/calendar.py`, import:

```python
from zer0share.query.repository import BaseParquetRepository, SqlFilter, TableSpec, date_range_filters, eq_filter
```

Replace the body of `trade_cal()` after the docstring with:

```python
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="trade_cal",
            path_parts=("trade_cal",),
            columns=TRADE_CAL_COLS,
            parquet_pattern="exchange=*/data.parquet",
            sync_table="trade_cal",
            order_by="exchange, cal_date",
            hive_partitioning=True,
        ),
    )
    filters: list[SqlFilter] = [eq_filter("exchange", exchange, TRADE_CAL_COLS)]
    filters.extend(date_range_filters("cal_date", None, start_date, end_date, TRADE_CAL_COLS))
    if is_open is not None:
        filters.append(eq_filter("is_open", parse_is_open(is_open), TRADE_CAL_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
```

- [ ] **Step 2: Refactor `index_weight`**

In `zer0share/query/equities.py`, import `date_range_filters` and `SqlFilter` from `zer0share.query.repository`.

Replace the manual SQL body of `index_weight()` with:

```python
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="index_weight",
            path_parts=("index_weight",),
            columns=INDEX_WEIGHT_COLS,
            parquet_pattern="index_code=*/date=*/data.parquet",
            sync_table="index_weight",
            order_by="index_code, con_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    )
    filters: list[SqlFilter] = []
    if index_code is not None:
        filters.append(eq_filter("index_code", index_code, INDEX_WEIGHT_COLS))
    filters.extend(date_range_filters("trade_date", trade_date, start_date, end_date, INDEX_WEIGHT_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
```

- [ ] **Step 3: Refactor `universe`**

Replace the manual SQL body of `universe()` with:

```python
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="universe",
            path_parts=("universe",),
            columns=UNIVERSE_COLS,
            parquet_pattern="name=*/date=*/data.parquet",
            sync_table="build-universe",
            order_by="universe, ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    )
    filters: list[SqlFilter] = []
    if universe is not None:
        filters.append(eq_filter("universe", universe, UNIVERSE_COLS))
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, UNIVERSE_COLS))
    filters.extend(date_range_filters("trade_date", trade_date, start_date, end_date, UNIVERSE_COLS))
    df = repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
    return format_date_columns(df, ["trade_date"])
```

Then adjust `BaseParquetRepository.ensure_exists()` if needed so the `universe` missing-data message remains exactly:

```python
if self.spec.sync_table == "build-universe":
    raise FileNotFoundError("universe data not found; run `python main.py build-universe` first")
```

For other tables, keep the existing `sync --table` message.

- [ ] **Step 4: Run targeted date-special tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_api.py::test_trade_cal_filters_open_days_and_formats_dates tests/test_api.py::test_trade_cal_invalid_date_range_raises_value_error tests/test_api.py::test_universe_filters_by_name_date_and_code tests/test_api.py::test_index_daily_returns_all_on_no_filter -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run full API tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_api.py -q
```

Expected: all API tests pass.

- [ ] **Step 6: Commit date-special refactor**

Run:

```bash
git add zer0share/query/calendar.py zer0share/query/equities.py zer0share/query/repository.py
git commit -m "refactor: use repositories for date-special queries"
```

Expected: commit succeeds with calendar, equities, and any repository message adjustment.

## Task 5: Final Verification and Cleanup

**Files:**
- Modify only files needed to remove unused imports or fix formatting introduced by previous tasks.
- Test: full test suite.

- [ ] **Step 1: Inspect imports and query module state**

Run:

```bash
rg -n "import duckdb|from zer0share.query._helpers import parse_fields|query_daily_partitioned|BaseParquetRepository|TableSpec" zer0share/query
```

Expected: `duckdb` imports remain only where still needed, `query_daily_partitioned()` remains as a compatibility helper, and repository imports are present in migrated modules.

- [ ] **Step 2: Run query repository tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_query_repository.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run API tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_api.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Run full test suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests -q
```

Expected: all tests pass.

- [ ] **Step 5: Check git status**

Run:

```bash
git status --short
```

Expected: only pre-existing unrelated user changes may remain, specifically the deleted `examples/local_query_api_smoke.py` if it was not restored by the user. All refactor files should be committed.

- [ ] **Step 6: Final commit if cleanup was needed**

If Step 1 required cleanup edits, run:

```bash
git add zer0share/query tests/test_query_repository.py tests/test_api.py
git commit -m "refactor: clean up query repository migration"
```

Expected: commit succeeds only if cleanup edits exist. If no cleanup edits exist, do not create an empty commit.
