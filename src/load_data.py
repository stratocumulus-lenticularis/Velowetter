import yaml
import os
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.compute as pc
import pyarrow as pa


DTYPES = {
    "FK_STANDORT": "int32",
    "VELO_IN": "float32",
    "VELO_OUT": "float32",
}

USECOLS = ["DATUM", "FK_STANDORT", "VELO_IN", "VELO_OUT"]

import json  # add at top of file

def load_bike_data(config_path: str, fk_ids: list[int]) -> pd.DataFrame:
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    static = cfg["data_sources"].get("static", {})
    dynamic = cfg["data_sources"].get("dynamic", {})
    sources = {**static, **dynamic}
    dynamic_names = set(dynamic.keys())

    dfs = []

    for name, url in sources.items():
        parquet_path = f"cache/{name}.parquet"
        os.makedirs("cache", exist_ok=True)

        # Always refresh dynamic sources
        if name in dynamic_names and os.path.exists(parquet_path):
            os.remove(parquet_path)

        # ── Check cache validity via stored metadata ──
        if os.path.exists(parquet_path):
            schema = pq.read_schema(parquet_path)        # reads only footer, no data
            cached_meta = schema.metadata or {}
            cached_ids = set(json.loads(cached_meta.get(b"requested_fk_ids", "[]")))
            if not set(fk_ids).issubset(cached_ids):
                print(f"Cache miss for {name}: new stations detected, rebuilding...")
                os.remove(parquet_path)

        if not os.path.exists(parquet_path):
            print(f"Converting CSV → Parquet for {name} ...")
            chunks = []
            for chunk in pd.read_csv(
                url,
                dtype=DTYPES,
                parse_dates=["DATUM"],
                usecols=USECOLS,
                chunksize=200_000,
            ):
                chunk = chunk[chunk["FK_STANDORT"].isin(fk_ids)]
                chunk["DATUM"] = chunk["DATUM"].dt.floor("h")
                chunk = (
                    chunk
                    .groupby(["DATUM", "FK_STANDORT"], sort=False)
                    [["VELO_IN", "VELO_OUT"]]
                    .sum()
                    .reset_index()
                )
                chunks.append(chunk)

            df = pd.concat(chunks, ignore_index=True)
            df = (
                df
                .groupby(["DATUM", "FK_STANDORT"], sort=False)
                [["VELO_IN", "VELO_OUT"]]
                .sum()
                .reset_index()
            )
            df["VELO_IN"] = df["VELO_IN"].astype("float32")
            df["VELO_OUT"] = df["VELO_OUT"].astype("float32")
            df["FK_STANDORT"] = df["FK_STANDORT"].astype("int32")

            # ── Store requested fk_ids in parquet metadata ──
            table = pa.Table.from_pandas(df)
            existing_meta = table.schema.metadata or {}
            updated_meta = {
                **existing_meta,
                b"requested_fk_ids": json.dumps(sorted(fk_ids)).encode()
            }
            table = table.replace_schema_metadata(updated_meta)
            pq.write_table(table, parquet_path)

        # PyArrow pushdown filter on the cached parquet
        table = pq.read_table(
            parquet_path,
            columns=USECOLS,
            filters=[("FK_STANDORT", "in", fk_ids)]
        )
        df = table.to_pandas()
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