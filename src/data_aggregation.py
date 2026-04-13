import numpy as np
import pandas as pd
from statsmodels.nonparametric.smoothers_lowess import lowess


def wide_to_long_directional(df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([
        df[["bezeichnung", "richtung_in", "DATUM", "VELO_IN"]]
          .rename(columns={"richtung_in": "richtung", "VELO_IN": "VELO"}),
        df[["bezeichnung", "richtung_out", "DATUM", "VELO_OUT"]]
          .rename(columns={"richtung_out": "richtung", "VELO_OUT": "VELO"}),
    ], ignore_index=True)


def fill_missing_timesteps(df: pd.DataFrame, freq: str = "15min") -> pd.DataFrame:
    """
    For each (bezeichnung, richtung) group, reindex to a complete time grid
    at `freq` resolution between the group's first and last timestamp.
    Missing timesteps are filled with NaN for VELO.
    """
    parts = []
    for (bez, richt), group in df.groupby(["bezeichnung", "richtung"], observed=True):
        group = group.set_index("DATUM").sort_index()
        full_grid = pd.date_range(start=group.index.min(), end=group.index.max(), freq=freq)
        group = group.reindex(full_grid)
        group["bezeichnung"] = bez
        group["richtung"] = richt
        group.index.name = "DATUM"
        parts.append(group.reset_index())
    return pd.concat(parts, ignore_index=True)


def _resample_group(df_sub: pd.DataFrame, col: str = "VELO") -> pd.DataFrame:
    """Shared resample logic for daily and weekly aggregation."""
    return df_sub[[col]].resample("1D").agg(
        VELO=(col, "sum"),
        OBS=(col, "count"),
    )


def _aggregate(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    Resample VELO to `freq` per (bezeichnung, richtung).
    Gaps (zero observations) are marked NaN.
    """
    df["DATUM"] = pd.to_datetime(df["DATUM"])
    parts = []
    for (bez, richt), df_sub in df.groupby(["bezeichnung", "richtung"], observed=True):
        df_sub = df_sub.set_index("DATUM").sort_index()
        agg = df_sub[["VELO"]].resample(freq).agg(
            VELO=("VELO", "sum"),
            OBS=("VELO", "count"),
        )
        agg["GAP"] = agg["OBS"] == 0
        agg["VELO"] = agg["VELO"].where(~agg["GAP"], other=float("nan"))
        agg["bezeichnung"] = bez
        agg["richtung"] = richt
        parts.append(agg.reset_index())
    return pd.concat(parts, ignore_index=True)


def make_daily_sums(df: pd.DataFrame) -> pd.DataFrame:
    return _aggregate(df, freq="1D")


def make_weekly_sums(df: pd.DataFrame) -> pd.DataFrame:
    return _aggregate(df, freq="W-MON")


def loess_smooth(dates: pd.Series, values: pd.Series, window_days: int = 365) -> list:
    """
    Apply LOESS smoothing with a window of `window_days` over the full date range.
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
    Add a VELO_TREND column by applying LOESS smoothing per (bezeichnung, richtung).
    """
    df["VELO"] = df["VELO"].astype("float64")
    df["VELO_TREND"] = pd.Series(dtype="float64")

    results = {}
    for (bez, richt), group in df.groupby(["bezeichnung", "richtung"], observed=True):
        group = group.sort_values("DATUM")
        trend = loess_smooth(group["DATUM"], group["VELO"], window_days=window_days)
        results.update(dict(zip(group.index, trend)))

    df["VELO_TREND"] = pd.Series(results, dtype="float32")
    return df
