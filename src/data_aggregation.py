import pandas as pd


def make_daily_sums(df: pd.DataFrame) -> pd.DataFrame:
    """
    Daily sums per (bezeichnung, richtung), using VELO only.
    RAM-efficient: resample per direction.
    """

    df = df.copy()
    df["DATUM"] = pd.to_datetime(df["DATUM"])

    parts = []

    for (bez, richt), df_sub in df.groupby(["bezeichnung", "richtung"]):
        df_sub = df_sub.set_index("DATUM").sort_index()

        daily = df_sub[["VELO"]].resample("1D").agg(
            VELO=("VELO", "sum"),
            OBS=("VELO", "count")
        )
        daily["GAP"] = daily["OBS"] == 0
        daily["VELO"] = daily["VELO"].where(~daily["GAP"], other=float("nan"))

        daily["bezeichnung"] = bez
        daily["richtung"] = richt
        daily = daily.reset_index()

        parts.append(daily)

    return pd.concat(parts, ignore_index=True)



def make_weekly_sums(df: pd.DataFrame) -> pd.DataFrame:
    """
    Weekly sums per (bezeichnung, richtung), using VELO only.
    RAM-efficient: resample per direction.
    """

    df = df.copy()
    df["DATUM"] = pd.to_datetime(df["DATUM"])

    parts = []

    for (bez, richt), df_sub in df.groupby(["bezeichnung", "richtung"]):
        df_sub = df_sub.set_index("DATUM").sort_index()

        weekly = df_sub[["VELO"]].resample("W-MON").agg(
            VELO=("VELO", "sum"),
            OBS=("VELO", "count")
        )
        weekly["GAP"] = weekly["OBS"] == 0
        weekly["VELO"] = weekly["VELO"].where(~weekly["GAP"], other=float("nan"))

        weekly["bezeichnung"] = bez
        weekly["richtung"] = richt
        weekly = weekly.reset_index()

        parts.append(weekly)

    return pd.concat(parts, ignore_index=True)


def wide_to_long_directional(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert VELO_IN/VELO_OUT into long format with correct directions.
    RAM-safe because it operates on one station at a time.
    """

    in_part = (
        df[["bezeichnung", "richtung_in", "DATUM", "VELO_IN"]]
        .rename(columns={"richtung_in": "richtung", "VELO_IN": "VELO"})
    )

    out_part = (
        df[["bezeichnung", "richtung_out", "DATUM", "VELO_OUT"]]
        .rename(columns={"richtung_out": "richtung", "VELO_OUT": "VELO"})
    )

    long_df = pd.concat([in_part, out_part], ignore_index=True)
    return long_df



import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess


def loess_smooth(dates: pd.Series, values: pd.Series, window_days: int = 365) -> list:
    """
    Apply LOESS smoothing with a window of `window_days` over the full date range.
    frac = window_days / total_days, clipped to a sensible minimum.
    Returns smoothed y values as a list (None where input was NaN).
    """
    total_days = (dates.max() - dates.min()).days
    frac = min(1.0, max(0.05, window_days / total_days)) if total_days > 0 else 1.0

    x = (dates - dates.min()).dt.days.values.astype(float)
    y = values.values.astype(float)
    mask = ~np.isnan(y)

    if mask.sum() < 10:
        return [None] * len(y)

    smoothed = np.full(len(y), np.nan)
    smoothed[mask] = lowess(y[mask], x[mask], frac=frac, return_sorted=False)

    return [round(float(v), 1) if not np.isnan(v) else None for v in smoothed]




def add_loess_trend(df: pd.DataFrame, window_days: int = 1460) -> pd.DataFrame:
    """
    Add a 'VELO_TREND' column to a daily or weekly dataframe by applying
    LOESS smoothing per (bezeichnung, richtung) group.
    """
    df = df.copy()
    df["VELO"] = df["VELO"].astype("float64")
    df["VELO_TREND"] = float("nan")
    df["VELO_TREND"] = df["VELO_TREND"].astype("float64")

    results = {}
    for (bez, richt), group in df.groupby(["bezeichnung", "richtung"]):
        group = group.sort_values("DATUM")
        trend = loess_smooth(group["DATUM"], group["VELO"], window_days=window_days)
        results.update(dict(zip(group.index, trend)))

    df["VELO_TREND"] = pd.Series(results, dtype="float64")
    return df


def fill_missing_timesteps(df: pd.DataFrame, freq: str = "15min") -> pd.DataFrame:
    """
    For each (bezeichnung, richtung) group, reindex to a complete time grid
    at `freq` resolution between the group's first and last timestamp.
    Missing timesteps are filled with NaN for VELO.
    """
    parts = []

    for (bez, richt), group in df.groupby(["bezeichnung", "richtung"]):
        group = group.set_index("DATUM").sort_index()

        full_grid = pd.date_range(
            start=group.index.min(),
            end=group.index.max(),
            freq=freq
        )

        group = group.reindex(full_grid)
        group["bezeichnung"] = bez
        group["richtung"] = richt
        group.index.name = "DATUM"
        parts.append(group.reset_index())

    return pd.concat(parts, ignore_index=True)
    