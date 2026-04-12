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


def run(fetch=True, list_stations=False):
    stations = [
        "Bertastrasse",
        "Bucheggplatz",
        "Hardbrücke Nord (Seite Altstetten)",
        "Hofwiesenstrasse",
#        "Letten / Dynamo", #seems to be empty
        "Lux-Guyer-Weg",
        "Mythenquai",
        "Scheuchzerstrasse",
        "Stadttunnel Nord",
        "Stadttunnel Süd (Barometer)",
        "Zollstrasse",
        "Quaibrücke Nord (Limmatseite)",       
        "Quaibrücke Süd (Seeseite)",
        
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

    if list_stations:
        lmd.print_all_stations(mapping)

    lmd.print_stations_for_selection(mapping, stations) 
    

    # Collect all FK_STANDORT IDs for all directions of each station
    all_fk_ids = lmd.get_fk_ids_for_stations(mapping, stations)  # new helper, see below

    if not all_fk_ids:
        print("No stations found in mapping, exiting.")
        return

    # Load all data in a single pass over the parquet files
    print(f"Loading data for {len(all_fk_ids)} FK_STANDORT IDs...")
    counts = ld.load_bike_data("config.yaml", all_fk_ids)
    merged = ld.merge_counts_with_metadata(counts, meta)
    merged.drop(columns=["FK_STANDORT", "id1"], inplace=True)
    del counts

    full_df = da.wide_to_long_directional(merged)
    del merged
    full_df["bezeichnung"] = full_df["bezeichnung"].astype("category")
    full_df["richtung"] = full_df["richtung"].astype("category")
    full_df["VELO"] = full_df["VELO"].astype("float32")

    print(f"Full dataset shape: {full_df.shape}")

    # Aggregate to 15-min sums per (bezeichnung, richtung, DATUM)
    agg = (
        full_df.groupby(["bezeichnung", "richtung", "DATUM"], as_index=False, observed=True)["VELO"]
               .sum()
    )
    del full_df

    agg = da.fill_missing_timesteps(agg, freq="1h")

    # Aggregate to daily and weekly sums
    daily = da.make_daily_sums(agg)
    weekly = da.make_weekly_sums(agg)
    del agg

    daily["DATUM"] = pd.to_datetime(daily["DATUM"], errors="coerce")
    weekly["DATUM"] = pd.to_datetime(weekly["DATUM"], errors="coerce")

    daily = daily.sort_values(["bezeichnung", "richtung", "DATUM"])
    weekly = weekly.sort_values(["bezeichnung", "richtung", "DATUM"])

    # Add LOESS trend column (1-year window)
    daily = da.add_loess_trend(daily, window_days=1460)
    weekly = da.add_loess_trend(weekly, window_days=1460)

    #some debugging
    #print(f"daily shape: {daily.shape}, date range: {daily['DATUM'].min()} → {daily['DATUM'].max()}")
    #print(f"weekly shape: {weekly.shape}, date range: {weekly['DATUM'].min()} → {weekly['DATUM'].max()}")


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
    list_stations = "--list-stations" in sys.argv
    run(fetch=fetch, list_stations=list_stations)
    