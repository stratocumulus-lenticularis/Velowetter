import yaml
import pandas as pd


def load_station_metadata(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["id1"] = pd.to_numeric(df["id1"], errors="coerce")
    df["bezeichnung"] = df["bezeichnung"].str.strip()
    df["richtung_out"] = df["richtung_out"].astype(str).str.    strip()
    return df
      

def build_station_mapping_both_directions(meta_df: pd.DataFrame) -> dict:
    mapping = {}

    for _, row in meta_df.iterrows():
        name = row["bezeichnung"]
        fk = row["id1"]

        # Richtung OUT als eigene Station
        rout = row["richtung_out"]
        if pd.notna(rout) and rout.strip() != "":
            mapping.setdefault((name, rout), []).append(fk)

        # Richtung IN als eigene Station
        rin = row["richtung_in"]
        if pd.notna(rin) and rin.strip() != "":
            mapping.setdefault((name, rin), []).append(fk)

    # Duplikate entfernen
    mapping = {k: sorted(set(v)) for k, v in mapping.items()}
    return mapping


def get_all_station_directions(mapping: dict) -> list[tuple[str, str]]:
    return list(mapping.keys())


def print_station_mapping(mapping):
    print("\nStation mapping (name + direction_out → FK_STANDORT IDs)\n")
    for (name, rout), ids in sorted(mapping.items()):
        print(f"{name:35} | {rout:20} → {ids}")

def get_fk_ids_for_stations(mapping: dict, station_names: list[str]) -> list[int]:
    """
    Return all FK_STANDORT IDs for every direction of the given station names.
    Replaces get_fk_standort_for_multiple() when direction selection is not needed.
    """
    ids = []
    station_names_set = set(station_names)

    for (name, direction), fk_ids in mapping.items():
        if name in station_names_set:
            ids.extend(fk_ids)

    missing = station_names_set - {name for (name, _) in mapping}
    for name in sorted(missing):
        print(f"Warning: no entry for station '{name}'")

    return sorted(set(ids))

def get_fk_standort_for_multiple(mapping: dict, station_direction_list: list[tuple[str, str]]) -> list[int]:
    """
    Select FK_STANDORT IDs for multiple (station_name, direction_out) pairs. 
    
    station_direction_list example:
    [
        ("Bucheggplatz", "Höngg"),
        ("Schulstrasse", "Bahnhof Oerlikon"),
        ("Lux-Guyer-Weg", "Wipkingen")
    ]
    """
    ids = []

    for name, direction_out in station_direction_list:
        key = (name, direction_out)
        if key in mapping:
            ids.extend(mapping[key])
        else:
            print(f"Warning: no entry for {name} → {direction_out}")

    return sorted(set(ids))


def print_stations_for_selection(mapping: dict, station_names: list[str]) -> None:
    """
    Print all directions and FK_STANDORT IDs for the selected station names.
    """
    station_names_set = set(station_names)
    grouped = {}

    for (name, direction), fk_ids in mapping.items():
        if name in station_names_set:
            grouped.setdefault(name, []).append((direction, fk_ids))

    print("\nSelected stations and directions:\n")
    print(f"  {'Station':<40} {'Direction':<30} IDs")
    print(f"  {'-'*40} {'-'*30} {'-'*15}")
    for name in station_names:  # preserve order from main.py
        if name not in grouped:
            print(f"  {'⚠ ' + name:<40} (no mapping found)")
            continue
        for i, (direction, fk_ids) in enumerate(sorted(grouped[name])):
            label = name if i == 0 else ""  # only print station name once
            print(f"  {label:<40} {direction:<30} {fk_ids}")
    print()


def print_all_stations(mapping: dict) -> None:
    """
    Print every station, direction and FK_STANDORT IDs found in the mapping.
    """
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