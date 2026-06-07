from loguru import logger
from zer0share.storage import SnapshotStore
from zer0share.sync import SyncRuntime
from zer0share.sync._jobs import SnapshotSyncJob, SyncJob
from zer0share.catalog import SW_CLASSIFY_SPEC, SW_MEMBER_SPEC, CI_MEMBER_SPEC


class IndustrySyncJob(SyncJob):
    table_name = "industry"
    supports_date_range = False

    def __init__(self, fetch_classify, fetch_member, store_classify: SnapshotStore, store_member: SnapshotStore):
        self._fetch_classify = fetch_classify
        self._fetch_member = fetch_member
        self._store_classify = store_classify
        self._store_member = store_member

    def run(self, rt: SyncRuntime, start_date=None, end_date=None) -> None:
        if rt.calendar.skip_if_not_trading("SSE"):
            return
        today = rt.calendar.today()
        try:
            df = self._fetch_classify()
            self._store_classify.write(df)
            rt.meta.update_last_date("sw_classify", today)
            logger.info(f"sw_classify 同步完成: {len(df)} 条")

            df = self._fetch_member()
            self._store_member.write(df)
            rt.meta.update_last_date("sw_member", today)
            logger.info(f"sw_member 同步完成: {len(df)} 条")
        except Exception as e:
            logger.error(f"industry 同步失败: {e}")
            rt.notifier.send(f"industry 同步失败: {e}")
            raise


def build_jobs(cfg, fetcher) -> list[SyncJob]:
    d = cfg.data_dir
    return [
        IndustrySyncJob(
            fetch_classify=fetcher.fetch_sw_classify,
            fetch_member=fetcher.fetch_sw_member,
            store_classify=SnapshotStore(d / "stock" / "industry" / "sw_classify" / "data.parquet"),
            store_member=SnapshotStore(d / "stock" / "industry" / "sw_member" / "data.parquet"),
        ),
        SnapshotSyncJob(
            table_name=CI_MEMBER_SPEC.name,
            spec=CI_MEMBER_SPEC,
            fetch=fetcher.fetch_ci_member,
            store=SnapshotStore(d / "stock" / "industry" / "ci_member" / "data.parquet"),
        ),
    ]
