import datetime as dt
from pathlib import Path

from zer0share.config import load_config
from zer0share.query import QueryContext
from zer0share.query import ricequant


def _check_date(value):
    if value is None:
        return
    try:
        dt.datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"invalid date format: {value!r}; expected YYYYMMDD") from exc


class RQLocal:
    def __init__(self, data_dir):
        self._ctx = QueryContext(Path(data_dir))

    def get_price(
        self,
        order_book_ids,
        start_date=None,
        end_date=None,
        frequency="1m",
        fields=None,
        adjust_type="none",
        skip_suspended=None,
        expect_df=True,
        time_slice=None,
        market="cn",
        limit=None,
        offset=None,
    ):
        if frequency != "1m":
            raise NotImplementedError("local rq_api.get_price currently only supports frequency='1m'")
        if market != "cn":
            raise NotImplementedError("local rq_api.get_price currently only supports market='cn'")
        if expect_df is not True:
            raise NotImplementedError("local rq_api.get_price currently only supports expect_df=True")
        if time_slice is not None:
            raise NotImplementedError("local rq_api.get_price does not support time_slice yet")
        if adjust_type != "none":
            raise ValueError("adjust_type must be 'none' for local RiceQuant minute data")
        _check_date(start_date)
        _check_date(end_date)
        if start_date is not None and end_date is not None and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        return ricequant.get_price(
            self._ctx,
            order_book_ids=order_book_ids,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            limit=limit,
            offset=offset,
        )

    def all_instruments(
        self,
        type=None,
        date=None,
        market="cn",
        fields=None,
        limit=None,
        offset=None,
    ):
        if date is not None:
            raise NotImplementedError("local rq_api.all_instruments does not support date filtering yet")
        if market != "cn":
            raise NotImplementedError("local rq_api.all_instruments currently only supports market='cn'")
        return ricequant.all_instruments(
            self._ctx,
            type=type,
            market=market,
            fields=fields,
            limit=limit,
            offset=offset,
        )


def rq_api(config_path="config/settings.toml") -> RQLocal:
    cfg = load_config(Path(config_path))
    return RQLocal(cfg.data_dir)
