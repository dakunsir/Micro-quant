"""RiceQuant history sync utilities and manifest tracking."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone
from pathlib import Path

import duckdb


def parse_bytes(value: str | None) -> int | None:
    """Parse strings like '50G', '512M', '1024K', '100B' (or bare int) to bytes.

    Returns None if value is None or empty string.
    Suffixes: G/GiB=1024^3, M/MiB=1024^2, K/KiB=1024, B=1
    """
    if value is None or value == "":
        return None
    value = value.strip()
    _suffixes = {
        "G": 1024**3,
        "GIB": 1024**3,
        "M": 1024**2,
        "MIB": 1024**2,
        "K": 1024,
        "KIB": 1024,
        "B": 1,
    }
    upper = value.upper()
    for suffix, multiplier in _suffixes.items():
        if upper.endswith(suffix):
            number_part = value[: -len(suffix)]
            return int(number_part) * multiplier
    # bare integer
    return int(value)


def month_chunks(start_date: str, end_date: str) -> list[tuple[str, str]]:
    """Split [start_date, end_date] into month-aligned chunks.

    Each chunk is (chunk_start, chunk_end) in YYYYMMDD format.
    First chunk starts at start_date, last chunk ends at end_date.
    Month boundaries: chunk ends on last day of the month, next starts on
    first of next month.

    Example:
        month_chunks("20260506", "20260621") == [
            ("20260506", "20260531"),
            ("20260601", "20260621"),
        ]
    """
    start_y = int(start_date[:4])
    start_m = int(start_date[4:6])
    start_d = int(start_date[6:])
    end_y = int(end_date[:4])
    end_m = int(end_date[4:6])
    end_d = int(end_date[6:])

    chunks: list[tuple[str, str]] = []
    cur_y, cur_m, cur_d = start_y, start_m, start_d

    while True:
        # last day of current month
        last_day = calendar.monthrange(cur_y, cur_m)[1]
        chunk_start = f"{cur_y:04d}{cur_m:02d}{cur_d:02d}"

        if (cur_y, cur_m) >= (end_y, end_m):
            # final chunk
            chunks.append((chunk_start, end_date))
            break
        else:
            chunk_end = f"{cur_y:04d}{cur_m:02d}{last_day:02d}"
            chunks.append((chunk_start, chunk_end))
            # advance to first day of next month
            if cur_m == 12:
                cur_y += 1
                cur_m = 1
            else:
                cur_m += 1
            cur_d = 1

    return chunks


_CREATE_DAYS_TABLE = """
CREATE TABLE IF NOT EXISTS ricequant_history_days (
    trade_date        VARCHAR PRIMARY KEY,
    status            VARCHAR,
    rows              INTEGER,
    symbols           INTEGER,
    parquet_size      BIGINT,
    bytes_used_before BIGINT,
    bytes_used_after  BIGINT,
    elapsed_seconds   DOUBLE,
    error             VARCHAR,
    reason            VARCHAR,
    recorded_at       TIMESTAMP
)
"""

_CREATE_CHUNKS_TABLE = """
CREATE TABLE IF NOT EXISTS ricequant_history_chunks (
    chunk_id    VARCHAR PRIMARY KEY,
    start_date  VARCHAR,
    end_date    VARCHAR,
    status      VARCHAR,
    recorded_at TIMESTAMP
)
"""


class RiceQuantHistoryManifest:
    """Tracks historical sync state in a DuckDB database."""

    def __init__(self, db_path: Path) -> None:
        """Open DuckDB at db_path, create tables if missing."""
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(db_path))
        self._conn.execute(_CREATE_DAYS_TABLE)
        self._conn.execute(_CREATE_CHUNKS_TABLE)

    def record_day_success(
        self,
        trade_date: str,
        rows: int,
        symbols: int,
        parquet_size: int,
        bytes_used_before: int,
        bytes_used_after: int,
        elapsed_seconds: float,
    ) -> None:
        """Upsert a successful day record."""
        now = datetime.now(timezone.utc)
        self._conn.execute(
            """
            INSERT INTO ricequant_history_days
                (trade_date, status, rows, symbols, parquet_size,
                 bytes_used_before, bytes_used_after, elapsed_seconds,
                 error, reason, recorded_at)
            VALUES (?, 'success', ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            ON CONFLICT (trade_date) DO UPDATE SET
                status            = excluded.status,
                rows              = excluded.rows,
                symbols           = excluded.symbols,
                parquet_size      = excluded.parquet_size,
                bytes_used_before = excluded.bytes_used_before,
                bytes_used_after  = excluded.bytes_used_after,
                elapsed_seconds   = excluded.elapsed_seconds,
                error             = excluded.error,
                reason            = excluded.reason,
                recorded_at       = excluded.recorded_at
            """,
            [trade_date, rows, symbols, parquet_size,
             bytes_used_before, bytes_used_after, elapsed_seconds, now],
        )

    def record_day_skipped(self, trade_date: str, reason: str) -> None:
        """Record a skipped day."""
        now = datetime.now(timezone.utc)
        self._conn.execute(
            """
            INSERT INTO ricequant_history_days
                (trade_date, status, rows, symbols, parquet_size,
                 bytes_used_before, bytes_used_after, elapsed_seconds,
                 error, reason, recorded_at)
            VALUES (?, 'skipped', NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
            ON CONFLICT (trade_date) DO UPDATE SET
                status      = excluded.status,
                reason      = excluded.reason,
                recorded_at = excluded.recorded_at
            """,
            [trade_date, reason, now],
        )

    def record_day_failure(self, trade_date: str, error: str) -> None:
        """Record a failed day."""
        now = datetime.now(timezone.utc)
        self._conn.execute(
            """
            INSERT INTO ricequant_history_days
                (trade_date, status, rows, symbols, parquet_size,
                 bytes_used_before, bytes_used_after, elapsed_seconds,
                 error, reason, recorded_at)
            VALUES (?, 'failed', NULL, NULL, NULL, NULL, NULL, NULL, ?, NULL, ?)
            ON CONFLICT (trade_date) DO UPDATE SET
                status      = excluded.status,
                error       = excluded.error,
                recorded_at = excluded.recorded_at
            """,
            [trade_date, error, now],
        )

    def get_day(self, trade_date: str) -> dict | None:
        """Return a dict with at minimum 'status', 'rows' keys. None if not found."""
        row = self._conn.execute(
            "SELECT * FROM ricequant_history_days WHERE trade_date = ?",
            [trade_date],
        ).fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in self._conn.description]
        return dict(zip(cols, row))

    def is_day_done(self, trade_date: str) -> bool:
        """Return True if trade_date has status='success' or status='skipped'."""
        row = self._conn.execute(
            "SELECT status FROM ricequant_history_days WHERE trade_date = ?",
            [trade_date],
        ).fetchone()
        if row is None:
            return False
        return row[0] in ("success", "skipped")

    def close(self) -> None:
        self._conn.close()

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> "RiceQuantHistoryManifest":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False
