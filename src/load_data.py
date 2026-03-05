import yaml
import os
import pandas as pd

def load_bike_data(config_path: str, fk_ids: list[int]) -> pd.DataFrame:
    """
    Load multi-year Zürich bike count data from URLs defined in config.yaml.
    Only selected stations are returned.
    """

    DTYPES = {
        "FK_STANDORT": "int32",
        "VELO_IN": "float32",
        "VELO_OUT": "float32",
        "FUSS_IN": "float32",
        "FUSS_OUT": "float32",
    }

    USECOLS = ["DATUM", "FK_STANDORT", "VELO_IN", "VELO_OUT", "FUSS_IN", "FUSS_OUT"]

    # --- load config ---
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    static = cfg["data_sources"].get("static", {})
    dynamic = cfg["data_sources"].get("dynamic", {})
    sources = {**static, **dynamic}

    dfs = []

    for name, url in sources.items():

        # Local cache filename
        parquet_path = f"cache/{name}.parquet"
        os.makedirs("cache", exist_ok=True)

        # --- If parquet exists: load it directly ---
        if os.path.exists(parquet_path):
            df = pd.read_parquet(
                parquet_path,
                columns=USECOLS
            )
        else:
            # --- Otherwise: load CSV and convert once ---
            print(f"Converting CSV → Parquet for {name} ...")

            df = pd.read_csv(
                url,
                dtype=DTYPES,
                parse_dates=["DATUM"],
                usecols=USECOLS
            )

            # Save for future runs
            df.to_parquet(parquet_path, index=False)

        # --- Filter early ---
        df = df[df["FK_STANDORT"].isin(fk_ids)]

        dfs.append(df)

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)




def merge_counts_with_metadata(counts_df: pd.DataFrame, meta_df: pd.DataFrame) -> pd.DataFrame:
    meta_small = meta_df[["id1", "bezeichnung", "richtung_out", "richtung_in"]].copy()

    meta_small["id1"] = pd.to_numeric(meta_small["id1"], errors="coerce")

    merged = counts_df.merge(
        meta_small,
        left_on="FK_STANDORT",
        right_on="id1",
        how="left"
    )

    return merged



def aggregate_by_station_direction_notusedanymore(merged_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert VELO_IN/VELO_OUT into directional VELO values using richtung_in/out,
    then aggregate per (bezeichnung, richtung, DATUM).
    """

    in_part = (
        merged_df[["bezeichnung", "richtung_in", "DATUM", "VELO_IN"]]
        .rename(columns={"richtung_in": "richtung", "VELO_IN": "VELO"})
    )

    out_part = (
        merged_df[["bezeichnung", "richtung_out", "DATUM", "VELO_OUT"]]
        .rename(columns={"richtung_out": "richtung", "VELO_OUT": "VELO"})
    )

    long_df = pd.concat([in_part, out_part], ignore_index=True)

    agg = (
        long_df.groupby(["bezeichnung", "richtung", "DATUM"], as_index=False)["VELO"]
               .sum()
    )

    return agg






"""
def combine_sensors(df: pd.DataFrame) -> pd.DataFrame:
    
    #Combine multiple sensors at the same Standort/direction into one time series.
    #Aggregates VELO_IN, VELO_OUT, FUSS_IN, FUSS_OUT by summing.
    
    agg_cols = ["VELO_IN", "VELO_OUT", "FUSS_IN", "FUSS_OUT"]

    df_combined = (
        df.groupby("DATUM")[agg_cols]
        .sum()
        .sort_index()
        .reset_index()
    )

    return df_combined
    
 """