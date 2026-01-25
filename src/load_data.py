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


