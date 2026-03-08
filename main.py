#run with 
# source /home/ubuntu/velowetter-env/bin/activate
# python main.py

# run with:
# source /home/ubuntu/velowetter-env/bin/activate
# python main.py             # downloads fresh dynamic data
# python main.py --no-fetch  # skips download, uses cached data

import sys
import yaml
import pandas as pd

from src.fetch import fetch_data
import src.load_data as ld
import src.load_metadata as lmd
import src.output as out
import src.data_aggregation as da


def run(fetch=True):
    stations = [
        ("Bucheggplatz", "Höngg"),
        ("Stadttunnel Nord", "Kasernenstrasse"),
        ("Stadttunnel Süd (Barometer)", "beide Richtungen"),
        ("Bucheggplatz", "Hofwiesenstrasse"),
        ("Lux-Guyer-Weg", "Wipkingen"),
        ("Lux-Guyer-Weg", "Innenstadt")
    ]

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    bucket = config["aws"]["bucket"]
    s3_prefix = config["aws"]["s3_prefix"]
    output_dir = config["output"]["local_output_dir"]
    station_standorte_file = config["data_sources"]["stations"]

    # Download fresh dynamic data (current year) unless suppressed
    if fetch:
        print("Downloading dynamic data...")
        fetch_data(static=False, dynamic=True)
    else:
        print("Skipping download, using cached data.")

    # Load metadata and build station -> FK_STANDORT mapping
    meta = lmd.load_station_metadata(station_standorte_file)
    mapping = lmd.build_station_mapping_both_directions(meta)

    # Collect all FK_STANDORT IDs across all stations in one go
    all_fk_ids = []
    for (station, direction) in stations:
        ids = mapping.get((station, direction), [])
        if not ids:
            print(f"Warning: no FK_STANDORT IDs for {station} -> {direction}, skipping.")
        all_fk_ids.extend(ids)
    all_fk_ids = sorted(set(all_fk_ids))

    if not all_fk_ids:
        print("No stations found in mapping, exiting.")
        return

    # Load all data in a single pass over the parquet files
    print(f"Loading data for {len(all_fk_ids)} FK_STANDORT IDs...")
    counts = ld.load_bike_data("config.yaml", all_fk_ids)
    merged = ld.merge_counts_with_metadata(counts, meta)
    del counts

    full_df = da.wide_to_long_directional(merged)
    del merged

    print(f"Full dataset shape: {full_df.shape}")

    # Aggregate to 15-min sums per (bezeichnung, richtung, DATUM)
    agg = (
        full_df.groupby(["bezeichnung", "richtung", "DATUM"], as_index=False)["VELO"]
               .sum()
    )
    del full_df

    # Aggregate to daily and weekly sums
    daily = da.make_daily_sums(agg)
    weekly = da.make_weekly_sums(agg)
    del agg

    daily["DATUM"] = pd.to_datetime(daily["DATUM"], errors="coerce")
    weekly["DATUM"] = pd.to_datetime(weekly["DATUM"], errors="coerce")

    daily = daily.sort_values(["bezeichnung", "richtung", "DATUM"])
    weekly = weekly.sort_values(["bezeichnung", "richtung", "DATUM"])

    print(f"Daily shape: {daily.shape}, Weekly shape: {weekly.shape}")

    out.plot_and_upload_interactive(
        df_daily=daily,
        df_weekly=weekly,
        output_dir=output_dir,
        bucket=bucket,
        s3_prefix=s3_prefix,
        html_filename="index.html"
    )


if __name__ == "__main__":
    fetch = "--no-fetch" not in sys.argv
    run(fetch=fetch)