from pathlib import Path

import pytest

from zer0share.ricequant_history import (
    RiceQuantHistoryManifest,
    month_chunks,
    parse_bytes,
)


def test_parse_bytes_supports_gib_suffixes():
    assert parse_bytes("50G") == 50 * 1024**3
    assert parse_bytes("512M") == 512 * 1024**2


def test_month_chunks_split_range():
    assert month_chunks("20260506", "20260621") == [
        ("20260506", "20260531"),
        ("20260601", "20260621"),
    ]


def test_manifest_records_day_success(tmp_path):
    manifest = RiceQuantHistoryManifest(tmp_path / "meta.duckdb")
    manifest.record_day_success(
        trade_date="20260506",
        rows=100,
        symbols=2,
        parquet_size=4096,
        bytes_used_before=10,
        bytes_used_after=20,
        elapsed_seconds=1.5,
    )
    row = manifest.get_day("20260506")
    assert row["status"] == "success"
    assert row["rows"] == 100
