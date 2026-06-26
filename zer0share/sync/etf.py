from zer0share.catalog import ETF_BASIC_SPEC
from zer0share.storage import SnapshotStore
from zer0share.sync._jobs import SnapshotSyncJob, SyncJob


def build_jobs(cfg, fetcher) -> list[SyncJob]:
    etf_dir = cfg.data_dir / "etf"
    return [
        SnapshotSyncJob(
            table_name=ETF_BASIC_SPEC.name,
            spec=ETF_BASIC_SPEC,
            fetch=fetcher.fetch_etf_basic,
            store=SnapshotStore(etf_dir / "etf_basic" / "data.parquet"),
            skip_non_trading=False,
        ),
    ]
