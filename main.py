# run with:
# source /home/ubuntu/velowetter-env/bin/activate
# python main.py                  # downloads fresh dynamic data
# python main.py --no-fetch       # skips download, uses cached data
# python main.py --all-stations   # load every station in the stations file
# python main.py --list-stations  # print available stations and exit
# python main.py --from 2025-01-01 --to 2025-12-31  # filter by date range (both bounds optional)

import sys
import yaml
import pandas as pd

from src.fetch import fetch_data
import src.load_data as ld
import src.load_metadata as lmd
import src.output as out
import src.data_aggregation as da


STATIONS = [
    "Bertastrasse",
    "Bucheggplatz",
    "Fischerweg",
    "Hardbrücke Nord (Seite Altstetten)",
    "Hofwiesenstrasse",
    "Lux-Guyer-Weg",
    "Mythenquai",
    "Scheuchzerstrasse",
    "Stadttunnel Nord",
    "Stadttunnel Süd (Barometer)",
    "Zollstrasse",
    "Quaibrücke Nord (Limmatseite)",
    "Quaibrücke Süd (Seeseite)",
]

LOESS_WINDOW_DAYS = 1460


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def resolve_stations(config: dict, all_stations: bool) -> tuple[list[str], dict, pd.DataFrame]:
    """
    Load metadata and return (station_names, mapping, meta).
    If all_stations is True, every station in the metadata file is used;
    otherwise the hardcoded STATIONS list is used.
    """
    meta = lmd.load_station_metadata(config["data_sources"]["stations"])
    mapping = lmd.build_station_mapping_both_directions(meta)

    if all_stations:
        stations = sorted({name for (name, _) in mapping})
        print(f"--all-stations: loading {len(stations)} stations from metadata file.")
    else:
        stations = STATIONS

    return stations, mapping, meta


def filter_by_date_range(
    df: pd.DataFrame,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    """
    Keep only stations that have at least some data within [date_from, date_to].
    A station qualifies if its date range overlaps with the requested window,
    i.e. it started before/on date_to AND ended on/after date_from.
    Either bound can be omitted to leave that end open.
    Applied after merging, before any heavy aggregation. Parquet cache
    is left untouched.
    """
    range_start = pd.Timestamp(date_from) if date_from else None
    range_end   = pd.Timestamp(date_to)   if date_to   else None

    bounds = df.groupby("bezeichnung")["DATUM"].agg(["min", "max"])

    mask = pd.Series(True, index=bounds.index)
    if range_start is not None:
        mask &= bounds["max"] >= range_start
    if range_end is not None:
        mask &= bounds["min"] <= range_end

    active  = bounds[mask].index
    dropped = sorted(set(bounds.index) - set(active))

    if range_start or range_end:
        window = f"{date_from or 'start'} → {date_to or 'end'}"
        if dropped:
            print(f"Filtered out {len(dropped)} station(s) with no data in {window}:")
            for name in dropped:
                print(f"  {name}  ({bounds.loc[name, 'min'].date()} → {bounds.loc[name, 'max'].date()})")
        print(f"Retained {len(active)} station(s) with data in {window}.")

    return df[df["bezeichnung"].isin(active)].copy()


def load_and_merge(config: dict, stations: list[str], mapping: dict, meta: pd.DataFrame) -> pd.DataFrame:
    fk_ids = lmd.get_fk_ids_for_stations(mapping, stations)
    if not fk_ids:
        raise RuntimeError("No stations found in mapping.")

    counts = ld.load_bike_data("config.yaml", fk_ids)
    lmd.print_stations_for_selection(mapping, stations, counts)

    merged = ld.merge_counts_with_metadata(counts, meta)
    merged.drop(columns=["FK_STANDORT", "id1"], inplace=True)
    return merged


def build_hourly(merged: pd.DataFrame) -> pd.DataFrame:
    long = da.wide_to_long_directional(merged)
    long["bezeichnung"] = long["bezeichnung"].astype("category")
    long["richtung"] = long["richtung"].astype("category")
    long["VELO"] = long["VELO"].astype("float32")

    agg = (
        long.groupby(["bezeichnung", "richtung", "DATUM"], as_index=False, observed=True)["VELO"]
            .sum()
    )
    return da.fill_missing_timesteps(agg, freq="1h")


def build_aggregates(hourly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = da.make_daily_sums(hourly)
    weekly = da.make_weekly_sums(hourly)

    for df in (daily, weekly):
        df["DATUM"] = pd.to_datetime(df["DATUM"], errors="coerce")
        df.sort_values(["bezeichnung", "richtung", "DATUM"], inplace=True)

    daily = da.add_loess_trend(daily, window_days=LOESS_WINDOW_DAYS)
    weekly = da.add_loess_trend(weekly, window_days=LOESS_WINDOW_DAYS)
    return daily, weekly


def run(
    fetch: bool = True,
    list_stations: bool = False,
    all_stations: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> None:
    config = load_config()

    if fetch:
        print("Downloading dynamic data...")
        fetch_data(static=False, dynamic=True)
    else:
        print("Skipping download, using cached data.")

    stations, mapping, meta = resolve_stations(config, all_stations)

    if list_stations:
        lmd.print_all_stations(mapping)

    merged = load_and_merge(config, stations, mapping, meta)
    merged = filter_by_date_range(merged, date_from=date_from, date_to=date_to)
    if merged.empty:
        raise RuntimeError("No stations found for the requested date range — nothing to process.")

    hourly = build_hourly(merged)
    del merged

    daily, weekly = build_aggregates(hourly)
    del hourly

    shared = dict(
        df_daily=daily,
        df_weekly=weekly,
        output_dir=config["output"]["local_output_dir"],
        bucket=config["aws"]["bucket"],
        s3_prefix=config["aws"]["s3_prefix"],
    )
    out.plot_and_upload_interactive(**shared, html_filename="index.html")
    out.plot_and_upload_overview(**shared, html_filename="overview.html")


if __name__ == "__main__":
    def _parse_arg(flag: str) -> str | None:
        if flag in sys.argv:
            idx = sys.argv.index(flag)
            try:
                val = sys.argv[idx + 1]
                pd.Timestamp(val)   # validate format early
                return val
            except (IndexError, ValueError):
                print(f"Usage: {flag} YYYY-MM-DD  (e.g. {flag} 2025-01-01)")
                sys.exit(1)
        return None

    run(
        fetch="--no-fetch" not in sys.argv,
        list_stations="--list-stations" in sys.argv,
        all_stations="--all-stations" in sys.argv,
        date_from=_parse_arg("--from"),
        date_to=_parse_arg("--to"),
    )