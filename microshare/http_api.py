"""Read-only HTTP API for local Microshare data."""

from __future__ import annotations

import json
import inspect
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from loguru import logger

from microshare.api import LocalPro, READ_ONLY_QUERY_METHODS
from microshare.config import Config, load_config
from microshare.coverage import build_stock_history_coverage
from microshare.query import calendar, etf, futures, index, industry, options, stock


_QUERY_FUNCTIONS = {
    "stock_basic": stock.stock_basic,
    "trade_cal": calendar.trade_cal,
    "daily": stock.daily,
    "adj_factor": stock.adj_factor,
    "daily_basic": stock.daily_basic,
    "stock_st": stock.stock_st,
    "suspend_d": stock.suspend_d,
    "stk_limit": stock.stk_limit,
    "index_daily": index.index_daily,
    "index_weight": index.index_weight,
    "sw_daily": index.sw_daily,
    "idx_anns": index.idx_anns,
    "universe": stock.universe,
    "pro_bar": stock.pro_bar,
    "index_classify": industry.index_classify,
    "index_member_all": industry.index_member_all,
    "ci_index_member": industry.ci_index_member,
    "fut_basic": futures.fut_basic,
    "fut_daily": futures.fut_daily,
    "fut_holding": futures.fut_holding,
    "fut_wsr": futures.fut_wsr,
    "fut_settle": futures.fut_settle,
    "fut_mapping": futures.fut_mapping,
    "ft_limit": futures.ft_limit,
    "fut_weekly": futures.fut_weekly,
    "fut_monthly": futures.fut_monthly,
    "fut_index_daily": futures.fut_index_daily,
    "fut_weekly_detail": futures.fut_weekly_detail,
    "opt_basic": options.opt_basic,
    "opt_daily": options.opt_daily,
    "etf_basic": etf.etf_basic,
    "etf_index": etf.etf_index,
    "fund_daily": etf.fund_daily,
    "fund_adj": etf.fund_adj,
    "etf_share_size": etf.etf_share_size,
    "etf_sh_cons": etf.etf_sh_cons,
}
_QUERY_PARAMETER_NAMES = {
    name: set(inspect.signature(function).parameters) - {"ctx"}
    for name, function in _QUERY_FUNCTIONS.items()
}
_BOOLEAN_PARAMETERS = {"is_hs", "is_open"}
_INTEGER_PARAMETERS = {"limit", "offset"}


def _parse_query_value(name: str, value: str) -> Any:
    if name in _INTEGER_PARAMETERS:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer") from exc
        if parsed < 0:
            raise ValueError(f"{name} must be non-negative")
        return parsed
    if name in _BOOLEAN_PARAMETERS:
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
        raise ValueError(f"{name} must be true, false, 1, or 0")
    return value


def _query_params(
    request: Request,
    api_name: str,
    default_limit: int,
    max_limit: int,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    allowed = _QUERY_PARAMETER_NAMES[READ_ONLY_QUERY_METHODS.get(api_name, api_name)]
    for name, value in request.query_params.multi_items():
        if name not in allowed:
            raise ValueError(f"unknown query parameter: {name}")
        parsed = _parse_query_value(name, value)
        if name in params:
            params[name] = f"{params[name]},{parsed}"
        else:
            params[name] = parsed

    limit = params.get("limit", default_limit)
    if limit > max_limit:
        raise ValueError(f"limit cannot exceed {max_limit}")
    params["limit"] = limit
    params.setdefault("offset", 0)
    return params


def _json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    # pandas emits valid JSON nulls for NaN and keeps date values serializable.
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _latest_dates(data_dir: Path) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    table_dirs = {
        "daily_kline": data_dir / "stock" / "daily_kline",
        "daily_basic": data_dir / "stock" / "daily_basic",
        "stock_st": data_dir / "stock" / "stock_st",
        "trade_cal": data_dir / "stock" / "trade_cal",
        "universe": data_dir / "stock" / "universe",
    }
    for name, table_dir in table_dirs.items():
        dates: list[str] = []
        if name == "trade_cal":
            for path in table_dir.glob("exchange=*/data.parquet"):
                try:
                    frame = pd.read_parquet(path, columns=["cal_date"])
                except (OSError, ValueError, KeyError):
                    continue
                dates.extend(
                    frame["cal_date"]
                    .astype(str)
                    .str.replace("-", "", regex=False)
                    .str.slice(0, 8)
                    .tolist()
                )
        elif name == "universe":
            for path in table_dir.glob("name=*/date=*/data.parquet"):
                dates.append(path.parent.name.removeprefix("date="))
        else:
            dates.extend(
                path.parent.name.removeprefix("date=")
                for path in table_dir.glob("date=*/data.parquet")
            )
        result[name] = max(dates) if dates else None
    return result


def _scheduler_status(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    phases = value.get("phases", {})
    phase_status = {
        name: phase.get("status")
        for name, phase in phases.items()
        if isinstance(name, str) and isinstance(phase, dict)
    }
    return {
        "run_id": value.get("run_id"),
        "status": value.get("status"),
        "started_at": value.get("started_at"),
        "finished_at": value.get("finished_at"),
        "current_trade_date": value.get("current_trade_date"),
        "effective_trade_date": value.get("effective_trade_date"),
        "phases": phase_status,
        "universe": (
            {"status": value["universe"].get("status")}
            if isinstance(value.get("universe"), dict)
            else None
        ),
    }


def _coverage_status(data_dir: Path, latest_dates: dict[str, str | None]) -> dict[str, Any]:
    candidates = [
        latest_dates.get(name)
        for name in ("daily_kline", "adj_factor", "daily_basic", "stock_st", "suspend_d", "stk_limit", "universe")
    ]
    end_date = max((value for value in candidates if value), default=None)
    if end_date is None:
        return {"status": "unavailable", "reason": "no stock history data"}
    try:
        report = build_stock_history_coverage(
            data_dir,
            end_date=end_date,
            validate_partitions=False,
        )
    except (FileNotFoundError, ValueError) as exc:
        return {"status": "unavailable", "reason": str(exc)}
    return {
        "status": "ok" if report["complete"] else "incomplete",
        "start_date": report["start_date"],
        "end_date": report["end_date"],
        "trade_days": report["trade_days"],
        "open_t1_ready_through": report["open_t1_ready_through"],
        "tables": {
            name: {
                "first_date": table_report["first_date"],
                "last_date": table_report["last_date"],
                "missing_partitions": table_report["missing_partitions"],
                "empty_partitions": table_report["empty_partitions"],
            }
            for name, table_report in report["tables"].items()
        },
    }


def create_app(config: Config | str | Path = "config/settings.toml") -> FastAPI:
    cfg = load_config(Path(config)) if not isinstance(config, Config) else config
    local_api = LocalPro(cfg.data_dir)

    app = FastAPI(
        title="Microshare Local Data API",
        version="0.1.0",
        description="Read-only access to locally synchronized Microshare data.",
    )

    @app.get("/healthz", tags=["system"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/status", tags=["system"])
    def status() -> dict[str, Any]:
        latest_dates = _latest_dates(cfg.data_dir)
        return {
            "status": "ok",
            "latest_dates": latest_dates,
            "coverage": _coverage_status(cfg.data_dir, latest_dates),
            "scheduler": _scheduler_status(cfg.scheduler.state_path),
        }

    @app.get("/v1/query/{api_name}", tags=["query"])
    def query(api_name: str, request: Request) -> dict[str, Any]:
        if api_name not in READ_ONLY_QUERY_METHODS:
            raise HTTPException(status_code=404, detail="unknown read-only api")
        try:
            params = _query_params(request, api_name, cfg.api.default_limit, cfg.api.max_limit)
            frame = local_api.query(api_name, **params)
            return {
                "api_name": api_name,
                "columns": list(frame.columns),
                "data": _json_records(frame),
                "count": len(frame),
                "limit": params["limit"],
                "offset": params["offset"],
            }
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"{api_name} local data is not synchronized")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except TypeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("local query failed for {}: {}", api_name, exc)
            raise HTTPException(status_code=500, detail="local query failed") from exc

    return app


def run_server(config_path: str | Path = "config/settings.toml") -> None:
    import uvicorn

    cfg = load_config(Path(config_path))
    uvicorn.run(
        create_app(cfg),
        host=cfg.api.host,
        port=cfg.api.port,
        log_config=None,
    )
