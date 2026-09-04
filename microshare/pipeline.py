from microshare.config import Config
from microshare.notifier import Notifier
from microshare.sources import DataSources
from microshare.storage import MetaStore
from microshare.sync import SyncRuntime
from microshare.sync._jobs import SyncJob
from microshare.trading_calendar import TradingCalendar


class Pipeline:
    def __init__(self, cfg: Config, sources: DataSources, notifier: Notifier):
        meta = MetaStore(cfg.db_path)
        calendar = TradingCalendar(meta)
        self._runtime = SyncRuntime(calendar=calendar, notifier=notifier, meta=meta)
        self._registry: dict[str, SyncJob] = {}
        self._build_registry(cfg, sources)

    def _build_registry(self, cfg: Config, sources: DataSources) -> None:
        from microshare.sync import calendar, stock, index, industry, futures, options, ricequant, etf
        for module in [calendar, stock, index, industry, futures, options, etf]:
            for job in module.build_jobs(cfg, sources.tushare):
                self._registry[job.table_name] = job
        for job in ricequant.build_jobs(cfg, sources):
            self._registry[job.table_name] = job

    def run(self, table_name: str, start_date: str | None = None, end_date: str | None = None) -> None:
        if table_name not in self._registry:
            raise ValueError(f"未知表: {table_name}")
        self._registry[table_name].run(self._runtime, start_date, end_date)

    def run_all(self, start_date: str | None = None, end_date: str | None = None) -> None:
        for job in self._registry.values():
            job.run(self._runtime, start_date, end_date)

    @property
    def registry(self) -> dict[str, SyncJob]:
        return self._registry

    def close(self) -> None:
        self._runtime.meta.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False
