from zer0share.catalog import ETF_BASIC_SPEC, ETF_INDEX_SPEC, FUND_DAILY_SPEC
from zer0share.storage import DailyPartitionStore, SnapshotStore
from zer0share.sync._jobs import DailySyncJob, SnapshotSyncJob, SyncJob


def build_jobs(cfg, fetcher) -> list[SyncJob]:
    etf_dir = cfg.data_dir / "etf"
    return [
        DailySyncJob(
            table_name=FUND_DAILY_SPEC.name,
            spec=FUND_DAILY_SPEC,
            fetch=fetcher.fetch_fund_daily,
            store=DailyPartitionStore(etf_dir / "fund_daily"),
        ),
        SnapshotSyncJob(
            table_name=ETF_BASIC_SPEC.name,
            spec=ETF_BASIC_SPEC,
            fetch=fetcher.fetch_etf_basic,
            store=SnapshotStore(etf_dir / "etf_basic" / "data.parquet"),
            skip_non_trading=False,
        ),
        SnapshotSyncJob(
            table_name=ETF_INDEX_SPEC.name,
            spec=ETF_INDEX_SPEC,
            fetch=fetcher.fetch_etf_index,
            store=SnapshotStore(etf_dir / "etf_index" / "data.parquet"),
            skip_non_trading=False,
        ),
    ]
