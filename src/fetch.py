import requests
import pandas as pd
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
data_dir = PROJECT_ROOT / "data"
data_dir.mkdir(parents=True, exist_ok=True)


def load_config():
    with open(PROJECT_ROOT / "config.yaml") as f:
        return yaml.safe_load(f)

def download_file(name, url): 
    r = requests.get(url) 
    r.raise_for_status() 
    file = data_dir / f"{name}.csv" 
    file.write_bytes(r.content) 
    print(f"Downloaded {name} → {file}") 

def fetch_data(static=False, dynamic=True):
    cfg = load_config()

    if static:
        for name, url in cfg["data_sources"]["static"].items():
            download_file(name,url)

    if dynamic:
        for name, url in cfg["data_sources"]["dynamic"].items():
            download_file(name,url)
