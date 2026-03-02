import pandas as pd

def make_daily_and_weekly_sums(df: pd.DataFrame):
    df = df.copy()
    df["DATUM"] = pd.to_datetime(df["DATUM"])

    agg_cols = ["VELO_IN", "VELO_OUT", "FUSS_IN", "FUSS_OUT"]

    # Daily sums
    daily = (
        df.set_index("DATUM")
          .groupby(["bezeichnung", "richtung"])[agg_cols]
          .resample("1D")
          .sum()
          .reset_index()
    )
    daily["TOTAL"] = daily["VELO_IN"] + daily["VELO_OUT"]

    # Weekly sums (Monday–Sunday)
    weekly = (
        df.set_index("DATUM")
          .groupby(["bezeichnung", "richtung"])[agg_cols]
          .resample("W-MON")
          .sum()
          .reset_index()
    )
    weekly["TOTAL"] = weekly["VELO_IN"] + weekly["VELO_OUT"]

    return daily, weekly


def make_daily_sums(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["DATUM"] = pd.to_datetime(df["DATUM"])

    agg_cols = ["VELO_IN", "VELO_OUT", "FUSS_IN", "FUSS_OUT"]

    daily = (
        df.set_index("DATUM")
          .groupby(["bezeichnung", "richtung"])[agg_cols]
          .resample("1D")
          .sum()
          .reset_index()
    )

    daily["TOTAL"] = daily["VELO_IN"] + daily["VELO_OUT"]
    return daily


def make_weekly_sums(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["DATUM"] = pd.to_datetime(df["DATUM"])

    agg_cols = ["VELO_IN", "VELO_OUT", "FUSS_IN", "FUSS_OUT"]

    weekly = (
        df.set_index("DATUM")
          .groupby(["bezeichnung", "richtung"])[agg_cols]
          .resample("W-MON")
          .sum()
          .reset_index()
    )

    weekly["TOTAL"] = weekly["VELO_IN"] + weekly["VELO_OUT"]
    return weekly

