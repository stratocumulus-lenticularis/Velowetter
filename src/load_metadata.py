import yaml
import pandas as pd


def load_station_metadata(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["id1"] = pd.to_numeric(df["id1"], errors="coerce")
    df["bezeichnung"] = df["bezeichnung"].str.strip()
    df["richtung_out"] = df["richtung_out"].astype(str).str.strip()
    return df


def build_station_mapping_both_directions(meta_df: pd.DataFrame) -> dict:
    mapping = {}
    for _, row in meta_df.iterrows():
        name = row["bezeichnung"]
        fk = row["id1"]
        for col in ("richtung_out", "richtung_in"):
            direction = row[col]
            if pd.notna(direction) and str(direction).strip():
                mapping.setdefault((name, str(direction).strip()), []).append(fk)
    return {k: sorted(set(v)) for k, v in mapping.items()}


def get_all_station_directions(mapping: dict) -> list[tuple[str, str]]:
    return list(mapping.keys())


def get_fk_ids_for_stations(mapping: dict, station_names: list[str]) -> list[int]:
    """Return all FK_STANDORT IDs for every direction of the given station names."""
    ids = []
    station_names_set = set(station_names)
    for (name, _), fk_ids in mapping.items():
        if name in station_names_set:
            ids.extend(fk_ids)

    missing = station_names_set - {name for (name, _) in mapping}
    for name in sorted(missing):
        print(f"Warning: no entry for station '{name}'")

    return sorted(set(ids))


def get_fk_standort_for_multiple(mapping: dict, station_direction_list: list[tuple[str, str]]) -> list[int]:
    """
    Select FK_STANDORT IDs for specific (station_name, direction) pairs.

    Example:
        [("Bucheggplatz", "Höngg"), ("Lux-Guyer-Weg", "Wipkingen")]
    """
    ids = []
    for name, direction in station_direction_list:
        key = (name, direction)
        if key in mapping:
            ids.extend(mapping[key])
        else:
            print(f"Warning: no entry for {name} → {direction}")
    return sorted(set(ids))


def print_station_mapping(mapping: dict) -> None:
    print("\nStation mapping (name + direction → FK_STANDORT IDs)\n")
    for (name, direction), ids in sorted(mapping.items()):
        print(f"{name:35} | {direction:20} → {ids}")


def print_stations_for_selection(mapping: dict, station_names: list[str], counts_df: pd.DataFrame = None) -> None:
    station_names_set = set(station_names)
    grouped = {}
    for (name, direction), fk_ids in mapping.items():
        if name in station_names_set:
            grouped.setdefault(name, []).append((direction, fk_ids))

    date_ranges = {}
    if counts_df is not None:
        for fk_id, grp in counts_df.groupby("FK_STANDORT", observed=True):
            date_ranges[fk_id] = (grp["DATUM"].min(), grp["DATUM"].max())

    print("\nSelected stations and directions:\n")
    print(f"  {'Station':<40} {'Direction':<30} {'IDs':<15} Date range")
    print(f"  {'-'*40} {'-'*30} {'-'*15} {'-'*25}")
    for name in station_names:
        if name not in grouped:
            print(f"  {'⚠ ' + name:<40} (no mapping found)")
            continue
        for i, (direction, fk_ids) in enumerate(sorted(grouped[name])):
            label = name if i == 0 else ""
            if date_ranges:
                mins = [date_ranges[fk][0] for fk in fk_ids if fk in date_ranges]
                maxs = [date_ranges[fk][1] for fk in fk_ids if fk in date_ranges]
                date_str = f"{min(mins).date()} → {max(maxs).date()}" if mins and maxs else "no data"
            else:
                date_str = ""
            print(f"  {label:<40} {direction:<30} {str(fk_ids):<15} {date_str}")
    print()


def print_all_stations(mapping: dict) -> None:
    grouped = {}
    for (name, direction), fk_ids in mapping.items():
        grouped.setdefault(name, []).append((direction, fk_ids))

    print("\nAll available stations and directions:\n")
    print(f"  {'Station':<40} {'Direction':<30} IDs")
    print(f"  {'-'*40} {'-'*30} {'-'*15}")
    for name in sorted(grouped):
        for i, (direction, fk_ids) in enumerate(sorted(grouped[name])):
            label = name if i == 0 else ""
            print(f"  {label:<40} {direction:<30} {fk_ids}")
    print()
