from __future__ import annotations

from dataclasses import dataclass

from zer0share.sources.ricequant import RiceQuantFetcher
from zer0share.sources.tushare import TushareFetcher


@dataclass(frozen=True)
class DataSources:
    tushare: TushareFetcher
    ricequant: RiceQuantFetcher | None = None


__all__ = ["DataSources", "RiceQuantFetcher", "TushareFetcher"]
