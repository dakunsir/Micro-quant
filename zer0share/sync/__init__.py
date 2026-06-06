from dataclasses import dataclass
from typing import TYPE_CHECKING

from zer0share.notifier import Notifier
from zer0share.storage import MetaStore

if TYPE_CHECKING:
    from zer0share.trading_calendar import TradingCalendar


@dataclass
class SyncRuntime:
    calendar: "TradingCalendar"
    notifier: Notifier
    meta: MetaStore
