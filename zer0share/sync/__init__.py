from dataclasses import dataclass

from zer0share.config import Config
from zer0share.fetcher import TushareFetcher
from zer0share.notifier import Notifier
from zer0share.storage import MetaStore


@dataclass
class SyncContext:
    cfg: Config
    fetcher: TushareFetcher
    notifier: Notifier
    meta: MetaStore
