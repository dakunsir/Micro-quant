import pandas as pd


def parse_is_open(value) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1"):
        return True
    if value in (0, "0"):
        return False
    raise ValueError("is_open must be one of True, False, 1, 0, '1', or '0'")


def format_date_columns(df: pd.DataFrame, date_columns: list[str]) -> pd.DataFrame:
    for column in date_columns:
        if column not in df.columns:
            continue
        formatted = pd.to_datetime(df[column], errors="coerce").dt.strftime("%Y%m%d")
        df[column] = formatted.astype(object)
        df.loc[formatted.isna(), column] = None
    return df
