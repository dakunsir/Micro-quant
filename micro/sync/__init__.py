from dataclasses import dataclass
from typing import TYPE_CHECKING

from micro.notifier import Notifier
from micro.storage import MetaStore

if TYPE_CHECKING:
    from micro.trading_calendar import TradingCalendar


@dataclass
class SyncRuntime:
    calendar: "TradingCalendar"
    notifier: Notifier
    meta: MetaStore
