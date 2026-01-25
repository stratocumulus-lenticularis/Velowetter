import yaml
import pandas as pd


def load_station_metadata(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["id1"] = pd.to_numeric(df["id1"], errors="coerce")
    df["bezeichnung"] = df["bezeichnung"].str.strip()
    df["richtung_out"] = df["richtung_out"].astype(str).str.    strip()
    return df
      

def build_station_mapping_by_out(meta_df: pd.DataFrame) -> dict:
    """ 
    Build mapping:
    (bezeichnung, richtung_out) → [FK_STANDORT IDs]
    Returns: 
    { 
        ("Bucheggplatz", "Höngg"): [16, 4237], 
        ("Bucheggplatz", "---"): [???], 
        ("Lux-Guyer-Weg", "Wipkingen"): [6, 2997], ... 
    } 
    """
    
    mapping = (
        meta_df.groupby(["bezeichnung", "richtung_out"])["id1"]
        .apply(lambda x: sorted(x.dropna().unique().tolist()))
        .to_dict()
    )
    return mapping



def print_station_mapping(mapping):
    print("\nStation mapping (name + direction_out → FK_STANDORT IDs)\n")
    for (name, rout), ids in sorted(mapping.items()):
        print(f"{name:35} | {rout:20} → {ids}")


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


