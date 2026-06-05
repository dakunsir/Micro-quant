import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import date, datetime, timezone
from pathlib import Path


def _parse(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:]))


class MetaStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(db_path))
        self._init_schema()

    def _init_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_meta (
                table_name  VARCHAR PRIMARY KEY,
                last_date   DATE,
                updated_at  TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_cal (
                exchange      VARCHAR,
                cal_date      DATE,
                is_open       BOOLEAN,
                pretrade_date DATE,
                PRIMARY KEY (exchange, cal_date)
            )
        """)

    def get_last_date(self, table_name: str) -> str | None:
        row = self._conn.execute(
            "SELECT last_date FROM sync_meta WHERE table_name = ?",
            [table_name]
        ).fetchone()
        return row[0].strftime("%Y%m%d") if row else None

    def update_last_date(self, table_name: str, last_date: str):
        self._conn.execute("""
            INSERT INTO sync_meta (table_name, last_date, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (table_name) DO UPDATE SET
                last_date = excluded.last_date,
                updated_at = excluded.updated_at
        """, [table_name, _parse(last_date), datetime.now(timezone.utc)])

    def __enter__(self) -> "MetaStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    def load_trade_cal_from_parquet(
        self, data_dir: Path, exchanges: list[str] | None = None
    ) -> None:
        trade_cal_dir = data_dir / "trade_cal"
        if not trade_cal_dir.exists():
            return
        allowed_exchanges = set(exchanges) if exchanges is not None else None
        self._conn.execute("BEGIN")
        try:
            self._conn.execute("DELETE FROM trade_cal")
            for exchange_dir in sorted(trade_cal_dir.iterdir()):
                if not exchange_dir.is_dir():
                    continue
                exchange = exchange_dir.name.removeprefix("exchange=")
                if allowed_exchanges is not None and exchange not in allowed_exchanges:
                    continue
                parquet_path = exchange_dir / "data.parquet"
                if not parquet_path.exists():
                    continue
                self._conn.execute(
                    """
                    INSERT INTO trade_cal
                    SELECT
                        exchange,
                        strptime(CAST(cal_date AS VARCHAR), '%Y%m%d')::DATE AS cal_date,
                        is_open,
                        CASE
                            WHEN pretrade_date IS NULL THEN NULL
                            ELSE strptime(CAST(pretrade_date AS VARCHAR), '%Y%m%d')::DATE
                        END AS pretrade_date
                    FROM read_parquet(?)
                    """,
                    [str(parquet_path)]
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def get_trading_days(
        self, exchange: str, start: str, end: str
    ) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT cal_date FROM trade_cal
            WHERE exchange = ?
              AND cal_date >= ?
              AND cal_date <= ?
              AND is_open = TRUE
            ORDER BY cal_date
            """,
            [exchange, _parse(start), _parse(end)]
        ).fetchall()
        return [row[0].strftime("%Y%m%d") for row in rows]

    def is_trading_day(self, exchange: str, cal_date: str) -> bool:
        """Check whether a given date is a trading day for an exchange.

        Returns True when the date is not covered by the calendar
        (conservative: don't skip syncs for dates we don't know about).
        """
        row = self._conn.execute(
            "SELECT is_open FROM trade_cal WHERE exchange = ? AND cal_date = ?",
            [exchange, _parse(cal_date)]
        ).fetchone()
        if row is None:
            return True
        return bool(row[0])

    def close(self):
        self._conn.close()


def write_daily_kline(data_dir: Path, trade_date: str, df: pd.DataFrame) -> None:
    partition_dir = data_dir / "daily_kline" / f"date={trade_date}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, partition_dir / "data.parquet")


def daily_kline_partition_exists(data_dir: Path, trade_date: str) -> bool:
    path = data_dir / "daily_kline" / f"date={trade_date}" / "data.parquet"
    return path.exists()


def read_daily_kline(data_dir: Path, trade_date: str) -> pd.DataFrame:
    path = data_dir / "daily_kline" / f"date={trade_date}" / "data.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pq.read_table(path).to_pandas()


def write_adj_factor(data_dir: Path, trade_date: str, df: pd.DataFrame) -> None:
    partition_dir = data_dir / "adj_factor" / f"date={trade_date}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, partition_dir / "data.parquet")


def adj_factor_partition_exists(data_dir: Path, trade_date: str) -> bool:
    path = data_dir / "adj_factor" / f"date={trade_date}" / "data.parquet"
    return path.exists()


def write_daily_partition(
    data_dir: Path, table_name: str, trade_date: str, df: pd.DataFrame
) -> None:
    partition_dir = data_dir / table_name / f"date={trade_date}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, partition_dir / "data.parquet")


def daily_partition_exists(data_dir: Path, table_name: str, trade_date: str) -> bool:
    path = data_dir / table_name / f"date={trade_date}" / "data.parquet"
    return path.exists()


def read_daily_partition(data_dir: Path, table_name: str, trade_date: str) -> pd.DataFrame:
    path = data_dir / table_name / f"date={trade_date}" / "data.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pq.read_table(path).to_pandas()


def write_index_weight(data_dir: Path, index_code: str, trade_date: str, df: pd.DataFrame) -> None:
    partition_dir = (
        data_dir / "index_weight" / f"index_code={index_code}" / f"date={trade_date}"
    )
    partition_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, partition_dir / "data.parquet")


def index_weight_partition_exists(data_dir: Path, index_code: str, trade_date: str) -> bool:
    path = (
        data_dir / "index_weight" / f"index_code={index_code}" / f"date={trade_date}" / "data.parquet"
    )
    return path.exists()


def write_universe(data_dir: Path, universe_name: str, trade_date: str, df: pd.DataFrame) -> None:
    partition_dir = (
        data_dir / "universe" / f"name={universe_name}" / f"date={trade_date}"
    )
    partition_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, partition_dir / "data.parquet")


def write_basic(data_dir: Path, df: pd.DataFrame) -> None:
    basic_dir = data_dir / "basic"
    basic_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, basic_dir / "data.parquet")


def read_basic(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "basic" / "data.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pq.read_table(path).to_pandas()


def write_opt_basic(data_dir: Path, df: pd.DataFrame) -> None:
    opt_basic_dir = data_dir / "opt_basic"
    opt_basic_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, opt_basic_dir / "data.parquet")


def write_trade_cal(data_dir: Path, exchange: str, df: pd.DataFrame) -> None:
    partition_dir = data_dir / "trade_cal" / f"exchange={exchange}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, partition_dir / "data.parquet")


def read_trade_cal(data_dir: Path, exchange: str) -> pd.DataFrame:
    path = data_dir / "trade_cal" / f"exchange={exchange}" / "data.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pq.read_table(path, schema=pq.read_schema(path)).to_pandas()


def write_sw_classify(data_dir: Path, df: pd.DataFrame) -> None:
    classify_dir = data_dir / "industry" / "sw_classify"
    classify_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, classify_dir / "data.parquet")


def read_sw_classify(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "industry" / "sw_classify" / "data.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pq.read_table(path).to_pandas()


def write_sw_member(data_dir: Path, df: pd.DataFrame) -> None:
    member_dir = data_dir / "industry" / "sw_member"
    member_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, member_dir / "data.parquet")


def read_sw_member(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "industry" / "sw_member" / "data.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pq.read_table(path).to_pandas()


def write_ci_member(data_dir: Path, df: pd.DataFrame) -> None:
    member_dir = data_dir / "industry" / "ci_member"
    member_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, member_dir / "data.parquet")


def read_ci_member(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "industry" / "ci_member" / "data.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pq.read_table(path).to_pandas()
