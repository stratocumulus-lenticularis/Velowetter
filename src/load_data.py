import yaml
import pandas as pd


def load_bike_data(config_path: str, fk_ids: list[int]) -> pd.DataFrame:
    """
    Load multi-year Zürich bike count data from URLs defined in config.yaml.
    Only selected stations are returned.

    Parameters
    ----------
    config_path : str
        Path to config.yaml
    stations : list[int]
        List of station IDs (ZST) to load

    Returns
    -------
    pd.DataFrame
        Combined dataframe with all selected stations and a 'year' column
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

    # --- load data ---
    dfs = []
    for name, url in sources.items():
        df = pd.read_csv(
            url,
            dtype=DTYPES, 
            parse_dates=["DATUM"],
            usecols=USECOLS
        )
        #df["DATUM"] = pd.to_datetime(df["DATUM"], errors="coerce")
        
        #print(f"Columns in {name}: {df.columns.tolist()}") # DEBUG
        #Columns in bike_counts2025: ['FK_STANDORT', 'DATUM', 'VELO_IN', 'VELO_OUT', 'FUSS_IN', 'FUSS_OUT', 'OST', 'NORD']

        # filter early to reduce memory
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



def aggregate_by_station_direction(merged_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate multiple instruments per (bezeichnung, richtung_out) and DATUM.
    """
    agg_cols = ["VELO_IN", "VELO_OUT", "FUSS_IN", "FUSS_OUT"]

    # grouped = (
        # merged_df
        # .groupby(["bezeichnung", "richtung_out", "DATUM"], as_index=False)[agg_cols]
        # .sum()
        # .sort_values(["bezeichnung", "richtung_out", "DATUM"])
    # )
    # Schritt 2: Aggregation nach bezeichnung + richtung (IN/OUT kombiniert)
    agg = (
        merged_df.groupby(["bezeichnung", "richtung", "DATUM"])
            [["VELO_IN", "VELO_OUT", "FUSS_IN", "FUSS_OUT"]]
            .sum()
            .reset_index()
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