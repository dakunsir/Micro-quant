"""
示例：查询米筐ETF分钟数据

使用前需要：
1. 在 config/settings.toml 中启用 ricequant 并配置凭据
2. 在 config/settings.toml 中启用 ricequant.etf_minute
3. 运行同步：
   python main.py sync --table ricequant_etf_basic
   python main.py sync --table ricequant_etf_minute --start-date 20240101 --end-date 20240105
"""

from pathlib import Path
from zer0share.rq_api import rq_api


def main():
    api = rq_api("config/settings.toml")

    # 查询所有ETF基础信息
    print("=" * 60)
    print("查询所有ETF基础信息")
    print("=" * 60)
    etf_list = api.all_etf_instruments(type="ETF")
    print(f"共 {len(etf_list)} 只ETF")
    print(etf_list.head(10))
    print()

    # 选择几只ETF查询分钟数据
    sample_etfs = etf_list["order_book_id"].head(3).tolist()
    print("=" * 60)
    print(f"查询ETF分钟数据: {sample_etfs}")
    print("=" * 60)

    # 查询分钟数据
    df = api.get_etf_price(
        order_book_ids=sample_etfs,
        start_date="20240102",
        end_date="20240102",
    )
    print(f"共 {len(df)} 条分钟数据")
    print(df.head(20))
    print()

    # 查询指定字段
    print("=" * 60)
    print("查询指定字段")
    print("=" * 60)
    df_selected = api.get_etf_price(
        order_book_ids=sample_etfs[0],
        start_date="20240102",
        end_date="20240102",
        fields="order_book_id,datetime,open,close,high,low,volume",
    )
    print(df_selected.head(20))
    print()

    # 查询每日汇总数据
    print("=" * 60)
    print("查询每日汇总数据（按交易日聚合volume和total_turnover）")
    print("=" * 60)
    df_daily = api.get_etf_daily_sum(
        order_book_ids=sample_etfs,
        fields=["volume", "total_turnover"],
        start_date="20240102",
        end_date="20240105",
    )
    print(df_daily)
    print()


if __name__ == "__main__":
    main()
