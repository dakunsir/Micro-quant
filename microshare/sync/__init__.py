from dataclasses import dataclass
from typing import TYPE_CHECKING

from microshare.notifier import Notifier
from microshare.storage import MetaStore

if TYPE_CHECKING:
    from microshare.trading_calendar import TradingCalendar


@dataclass
class SyncRuntime:
    calendar: "TradingCalendar"
    notifier: Notifier
    meta: MetaStore
