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

        daily = df_sub[["VELO"]].resample("1D").sum()

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

        weekly = df_sub[["VELO"]].resample("W-MON").sum()

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

