from microshare.catalog import (
    ADJ_FACTOR_SPEC, BASIC_SPEC, DAILY_BASIC_SPEC, DAILY_KLINE_SPEC,
    STK_LIMIT_SPEC, STOCK_ST_SPEC, SUSPEND_D_SPEC,
)
from microshare.storage import DailyPartitionStore, SnapshotStore
from microshare.sync._jobs import DailySyncJob, SnapshotSyncJob, SyncJob


def build_jobs(cfg, fetcher) -> list[SyncJob]:
    d = cfg.data_dir
    return [
        SnapshotSyncJob(
            table_name=BASIC_SPEC.name, spec=BASIC_SPEC,
            fetch=fetcher.fetch_basic,
            store=SnapshotStore(d / "stock" / "basic" / "data.parquet"),
            skip_non_trading=False,
        ),
        DailySyncJob(
            table_name=DAILY_KLINE_SPEC.name, spec=DAILY_KLINE_SPEC,
            fetch=fetcher.fetch_daily_kline,
            store=DailyPartitionStore(d / "stock" / "daily_kline"),
        ),
        DailySyncJob(
            table_name=ADJ_FACTOR_SPEC.name, spec=ADJ_FACTOR_SPEC,
            fetch=fetcher.fetch_adj_factor,
            store=DailyPartitionStore(d / "stock" / "adj_factor"),
        ),
        DailySyncJob(
            table_name=DAILY_BASIC_SPEC.name, spec=DAILY_BASIC_SPEC,
            fetch=fetcher.fetch_daily_basic,
            store=DailyPartitionStore(d / "stock" / "daily_basic"),
        ),
        DailySyncJob(
            table_name=STOCK_ST_SPEC.name, spec=STOCK_ST_SPEC,
            fetch=fetcher.fetch_stock_st,
            store=DailyPartitionStore(d / "stock" / "stock_st"),
            write_empty=True,
        ),
        DailySyncJob(
            table_name=SUSPEND_D_SPEC.name, spec=SUSPEND_D_SPEC,
            fetch=fetcher.fetch_suspend_d,
            store=DailyPartitionStore(d / "stock" / "suspend_d"),
            write_empty=True,
        ),
        DailySyncJob(
            table_name=STK_LIMIT_SPEC.name, spec=STK_LIMIT_SPEC,
            fetch=fetcher.fetch_stk_limit,
            store=DailyPartitionStore(d / "stock" / "stk_limit"),
        ),
    ]
