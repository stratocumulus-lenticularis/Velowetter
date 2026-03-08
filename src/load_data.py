import yaml
import os
import pandas as pd
import pyarrow.parquet as pq


DTYPES = {
    "FK_STANDORT": "int32",
    "VELO_IN": "float32",
    "VELO_OUT": "float32",
}

USECOLS = ["DATUM", "FK_STANDORT", "VELO_IN", "VELO_OUT"]


def load_bike_data(config_path: str, fk_ids: list[int]) -> pd.DataFrame:
    """
    Load multi-year Zürich bike count data from URLs defined in config.yaml.
    Only selected stations are returned. Uses PyArrow pushdown filtering to
    avoid loading irrelevant rows into RAM.
    """
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    static = cfg["data_sources"].get("static", {})
    dynamic = cfg["data_sources"].get("dynamic", {})
    sources = {**static, **dynamic}

    dfs = []

    for name, url in sources.items():
        parquet_path = f"cache/{name}.parquet"
        os.makedirs("cache", exist_ok=True)

        if not os.path.exists(parquet_path):
            print(f"Converting CSV → Parquet for {name} ...")
            df = pd.read_csv(
                url,
                dtype=DTYPES,
                parse_dates=["DATUM"],
                usecols=USECOLS
            )
            df.to_parquet(parquet_path, index=False)

        # Use PyArrow to filter rows at read time — never loads irrelevant data
        table = pq.read_table(
            parquet_path,
            columns=USECOLS,
            filters=[("FK_STANDORT", "in", fk_ids)]
        )
        df = table.to_pandas()

        # Restore dtypes lost during parquet round-trip
        df["VELO_IN"] = df["VELO_IN"].astype("float32")
        df["VELO_OUT"] = df["VELO_OUT"].astype("float32")

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
    



