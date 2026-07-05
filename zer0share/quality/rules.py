from __future__ import annotations

import pandas as pd

from zer0share.quality.models import QualityFinding, Severity


def _sample(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    if columns is not None:
        available = [column for column in columns if column in df.columns]
        if available:
            df = df[available]
    return df.head(limit).to_dict("records")


def check_required_columns(
    table: str,
    date: str | None,
    df: pd.DataFrame,
    required_columns: list[str],
) -> list[QualityFinding]:
    missing = [column for column in required_columns if column not in df.columns]
    if not missing:
        return []

    return [
        QualityFinding(
            table=table,
            date=date,
            severity=Severity.FAIL,
            rule="required_columns",
            count=len(missing),
            message=f"missing required columns: {', '.join(missing)}",
            sample=[{"missing_columns": missing}],
        )
    ]


def check_duplicate_key(
    table: str,
    date: str | None,
    df: pd.DataFrame,
    key_columns: tuple[str, ...],
) -> list[QualityFinding]:
    if any(column not in df.columns for column in key_columns):
        return []

    duplicated = df[df.duplicated(list(key_columns), keep=False)]
    if duplicated.empty:
        return []

    return [
        QualityFinding(
            table=table,
            date=date,
            severity=Severity.FAIL,
            rule="duplicate_key",
            count=len(duplicated),
            message=f"duplicate rows for key columns: {', '.join(key_columns)}",
            sample=_sample(duplicated, list(key_columns)),
        )
    ]


def check_market_data_values(
    table: str,
    date: str | None,
    df: pd.DataFrame,
) -> list[QualityFinding]:
    findings: list[QualityFinding] = []

    price_columns = ["open", "high", "low", "close"]
    if all(column in df.columns for column in price_columns):
        bad_prices = df[
            df[price_columns].isna().any(axis=1)
            | (df[price_columns] <= 0).any(axis=1)
        ]
        if not bad_prices.empty:
            findings.append(
                QualityFinding(
                    table=table,
                    date=date,
                    severity=Severity.FAIL,
                    rule="positive_prices",
                    count=len(bad_prices),
                    message="open, high, low, and close must be non-null and greater than 0",
                    sample=_sample(bad_prices, ["ts_code", "trade_date", *price_columns]),
                )
            )

        bad_ohlc = df[
            (df["high"] < df[["open", "close"]].max(axis=1))
            | (df["low"] > df[["open", "close"]].min(axis=1))
            | (df["high"] < df["low"])
        ]
        if not bad_ohlc.empty:
            findings.append(
                QualityFinding(
                    table=table,
                    date=date,
                    severity=Severity.FAIL,
                    rule="ohlc_relationship",
                    count=len(bad_ohlc),
                    message="high/low relationship is invalid",
                    sample=_sample(bad_ohlc, ["ts_code", "trade_date", *price_columns]),
                )
            )

    for column in ("vol", "amount"):
        if column not in df.columns:
            continue
        bad_volume = df[df[column].isna() | (df[column] <= 0)]
        if not bad_volume.empty:
            findings.append(
                QualityFinding(
                    table=table,
                    date=date,
                    severity=Severity.WARN,
                    rule=f"positive_{column}",
                    count=len(bad_volume),
                    message=f"{column} should be greater than 0",
                    sample=_sample(bad_volume, ["ts_code", "trade_date", column]),
                )
            )

    if "pre_close" in df.columns and "pct_chg" in df.columns and "close" in df.columns:
        valid_base = df["pre_close"] > 0
        expected_pct = (df["close"] / df["pre_close"] - 1) * 100
        bad_pct = df[valid_base & ((expected_pct - df["pct_chg"]).abs() > 0.01)]
        if not bad_pct.empty:
            findings.append(
                QualityFinding(
                    table=table,
                    date=date,
                    severity=Severity.FAIL,
                    rule="pct_chg_consistency",
                    count=len(bad_pct),
                    message="pct_chg differs from close/pre_close by more than 0.01 percentage points",
                    sample=_sample(bad_pct, ["ts_code", "trade_date", "close", "pre_close", "pct_chg"]),
                )
            )

    return findings


def check_adjustment_factor_values(
    table: str,
    date: str | None,
    df: pd.DataFrame,
) -> list[QualityFinding]:
    if "adj_factor" not in df.columns:
        return [
            QualityFinding(
                table=table,
                date=date,
                severity=Severity.FAIL,
                rule="positive_adj_factor",
                count=1,
                message="adj_factor column is missing",
                sample=[],
            )
        ]

    bad = df[df["adj_factor"].isna() | (df["adj_factor"] <= 0)]
    if bad.empty:
        return []

    return [
        QualityFinding(
            table=table,
            date=date,
            severity=Severity.FAIL,
            rule="positive_adj_factor",
            count=len(bad),
            message="adj_factor must be non-null and greater than 0",
            sample=_sample(bad, ["ts_code", "trade_date", "adj_factor"]),
        )
    ]
