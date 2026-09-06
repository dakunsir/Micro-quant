from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from microshare.http_api import create_app
from microshare.storage import write_trade_cal


def _config(tmp_path: Path, *, host: str = "127.0.0.1") -> Path:
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        f"""
[tushare]
token = "test"

[paths]
data_dir = "{tmp_path.as_posix()}"
db_path = "{(tmp_path / 'meta.duckdb').as_posix()}"
log_path = "{(tmp_path / 'pipeline.log').as_posix()}"

[api]
host = "{host}"
port = 8787
default_limit = 1
max_limit = 2

[scheduler]
enabled = false
timezone = "Asia/Shanghai"
run_time = "18:30"

[notifier]
enabled = false
""",
        encoding="utf-8",
    )
    return config_path


def test_health_status_and_read_only_query(tmp_path):
    write_trade_cal(
        tmp_path,
        "SSE",
        pd.DataFrame(
            {
                "exchange": ["SSE", "SSE"],
                "cal_date": ["20240102", "20240103"],
                "is_open": [True, True],
                "pretrade_date": ["20240101", "20240102"],
            }
        ),
    )
    client = TestClient(create_app(_config(tmp_path)))

    assert client.get("/healthz").json() == {"status": "ok"}
    status = client.get("/v1/status")
    assert status.status_code == 200
    assert status.json()["latest_dates"]["trade_cal"] == "20240103"
    assert status.json()["coverage"]["status"] == "unavailable"

    response = client.get(
        "/v1/query/trade_cal",
        params={"exchange": "SSE", "start_date": "20240102", "end_date": "20240103"},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["limit"] == 1

    assert client.post("/v1/query/trade_cal").status_code == 405


def test_query_rejects_unknown_api_parameter_and_limit(tmp_path):
    client = TestClient(create_app(_config(tmp_path)))

    assert client.get("/v1/query/trade_cal", params={"sql": "select 1"}).status_code == 400
    assert client.get("/v1/query/trade_cal", params={"limit": 3}).status_code == 400
    assert client.get("/v1/query/not_a_query").status_code == 404


def test_query_maps_missing_data_to_not_found(tmp_path):
    client = TestClient(create_app(_config(tmp_path)))
    response = client.get("/v1/query/daily", params={"ts_code": "000001.SZ", "trade_date": "20240102"})

    assert response.status_code == 404
    assert "not synchronized" in response.json()["detail"]


def test_api_host_must_be_loopback(tmp_path):
    with pytest.raises(ValueError, match="回环地址"):
        create_app(_config(tmp_path, host="0.0.0.0"))
