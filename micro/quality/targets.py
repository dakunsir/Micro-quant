from __future__ import annotations

from dataclasses import dataclass

from micro.catalog import (
    ADJ_FACTOR_SPEC,
    DAILY_KLINE_SPEC,
    FUND_ADJ_SPEC,
    FUND_DAILY_SPEC,
    FUT_DAILY_SPEC,
    INDEX_DAILY_SPEC,
    OPT_DAILY_SPEC,
)
from micro.query.repository import TableSpec


@dataclass(frozen=True)
class QualityTarget:
    table: str
    market: str
    kind: str
    spec: TableSpec
    primary_key: tuple[str, ...] = ("ts_code", "trade_date")
    price_columns: tuple[str, ...] = ("open", "high", "low", "close")
    volume_columns: tuple[str, ...] = ("vol", "amount")
    related_table: str | None = None


QUALITY_TARGETS: dict[str, QualityTarget] = {
    "daily_kline": QualityTarget("daily_kline", "stock", "market_data", DAILY_KLINE_SPEC),
    "adj_factor": QualityTarget(
        "adj_factor",
        "stock",
        "adjustment",
        ADJ_FACTOR_SPEC,
        price_columns=(),
        volume_columns=(),
        related_table="daily_kline",
    ),
    "index_daily": QualityTarget("index_daily", "index", "market_data", INDEX_DAILY_SPEC),
    "fund_daily": QualityTarget("fund_daily", "etf", "market_data", FUND_DAILY_SPEC),
    "fund_adj": QualityTarget(
        "fund_adj",
        "etf",
        "adjustment",
        FUND_ADJ_SPEC,
        price_columns=(),
        volume_columns=(),
        related_table="fund_daily",
    ),
    "fut_daily": QualityTarget("fut_daily", "futures", "market_data", FUT_DAILY_SPEC),
    "opt_daily": QualityTarget("opt_daily", "options", "market_data", OPT_DAILY_SPEC),
}


def get_targets(names: list[str]) -> list[QualityTarget]:
    unknown = [name for name in names if name not in QUALITY_TARGETS]
    if unknown:
        raise ValueError(f"unknown quality table: {', '.join(unknown)}")
    return [QUALITY_TARGETS[name] for name in names]


def select_targets(
    *,
    table: str | None = None,
    market: str | None = None,
    all_targets: bool = False,
) -> list[QualityTarget]:
    selectors = [table is not None, market is not None, all_targets]
    if sum(selectors) != 1:
        raise ValueError("select exactly one of table, market, or all_targets")
    if table is not None:
        return get_targets([table])
    if market is not None:
        targets = [target for target in QUALITY_TARGETS.values() if target.market == market]
        if not targets:
            raise ValueError(f"unknown quality market: {market}")
        return targets
    return list(QUALITY_TARGETS.values())
