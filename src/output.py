import os
import matplotlib.pyplot as plt
import pandas as pd
import boto3
import re
import gc
import json

import plotly.io as pio
import plotly.graph_objects as go

import unicodedata
def normalize(s):
    return unicodedata.normalize("NFC", s)


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]+", "", text)
    return text


def plot_and_upload_plot_notinuseanymore(
    df: pd.DataFrame,
    output_dir: str,
    bucket: str,
    s3_prefix: str,
    page_title: str = "Bike Counts – All Stations",
    html_filename: str = "index.html"
):
    df = df.copy()
    df["DATUM"] = pd.to_datetime(df["DATUM"])

    if "VELO" not in df.columns:
        raise ValueError("Expected column 'VELO' in df (long format with direction).")

    os.makedirs(output_dir, exist_ok=True)
    s3 = boto3.client("s3")

    png_files = []  # (bezeichnung, richtung, filename)

    # group by logical station + direction
    groups = df.groupby(["bezeichnung", "richtung"])

    for (name, direction), sub in groups:
        sub = sub.sort_values("DATUM")

        safe_name = slugify(name)
        safe_dir = slugify(direction)
        png_filename = f"{safe_name}__{safe_dir}.png"
        png_local_path = os.path.join(output_dir, png_filename)
        png_s3_key = f"{s3_prefix}/{png_filename}"

        plt.figure(figsize=(14, 7))
        plt.plot(sub["DATUM"], sub["VELO"], label=f"{name} → {direction}")

        plt.title(f"Bike Counts – {name} → {direction}")
        plt.xlabel("Date")
        plt.ylabel("Bikes per direction")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()

        plt.savefig(png_local_path, dpi=150)
        plt.close("all")
        gc.collect()

        png_files.append((name, direction, png_filename))

        with open(png_local_path, "rb") as f:
            s3.put_object(
                Bucket=bucket,
                Key=png_s3_key,
                Body=f,
                ContentType="image/png",
                CacheControl="no-cache"
            )

    # --- HTML generation stays almost the same ---
    html_local_path = os.path.join(output_dir, html_filename)
    html_s3_key = f"{s3_prefix}/{html_filename}"

    html_header = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{page_title}</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 20px;
      background-color: #f7f7f7;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
      background: #ffffff;
      padding: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }}
    h1 {{
      font-size: 1.8rem;
      margin-bottom: 1.5rem;
    }}
    h2 {{
      font-size: 1.3rem;
      margin-top: 2rem;
      margin-bottom: 0.5rem;
    }}
    .plot-wrapper {{
      text-align: center;
      margin-bottom: 2rem;
    }}
    .plot-wrapper img {{
      max-width: 100%;
      height: auto;
      border: 1px solid #ddd;
      cursor: pointer;
    }}
    .caption {{
      margin-top: 0.4rem;
      font-size: 0.9rem;
      color: #555;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>{page_title}</h1>
"""

    html_footer = """
  </div>
</body>
</html>
"""

    html_body = ""
    for name, direction, png_filename in png_files:
        title = f"{name} → {direction}"
        html_body += f"""
    <h2>{title}</h2>
    <div class="plot-wrapper">
      <a href="{png_filename}" target="_blank">
        <img src="{png_filename}" alt="Bike counts for {title}">
      </a>
      <div class="caption">Click to view full-size image</div>
    </div>
"""

    with open(html_local_path, "w", encoding="utf-8") as f:
        f.write(html_header + html_body + html_footer)

    with open(html_local_path, "rb") as f:
        s3.put_object(
            Bucket=bucket,
            Key=html_s3_key,
            Body=f,
            ContentType="text/html",
            CacheControl="no-cache"
        )

    print("All station-direction plots generated.")
    print(f"HTML page saved to {html_local_path}")
    print(f"Uploaded to s3://{bucket}/{s3_prefix}/")



import os
import json
import boto3
import pandas as pd
import plotly.io as pio


import os
import json
import boto3
import pandas as pd
import plotly.io as pio

import numpy as np


def plot_and_upload_interactive(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    output_dir: str,
    bucket: str,
    s3_prefix: str,
    make_daily_plot,
    make_weekly_plot,
    page_title: str = "Bike Counts – Interactive",
    html_filename: str = "index.html"
):
    """
    Generate an interactive Plotly dashboard (one plot at a time) and upload it to S3.

    The dashboard allows selecting:
        - station
        - direction
        - aggregation (daily / weekly)

    All Plotly figures are converted to JSON and rendered client‑side with Plotly.newPlot().
    This avoids hidden divs, duplicated scripts, and layout issues.
    """

    # ----------------------------------------------------------------------
    # 1. Prepare output directory and S3 client
    # ----------------------------------------------------------------------
    os.makedirs(output_dir, exist_ok=True)
    s3 = boto3.client("s3")

    # ----------------------------------------------------------------------
    # 2. Normalize station/direction names
    # ----------------------------------------------------------------------
    df_daily["bezeichnung"] = df_daily["bezeichnung"].astype(str).str.strip()
    df_daily["richtung"] = df_daily["richtung"].astype(str).str.strip()
    df_weekly["bezeichnung"] = df_weekly["bezeichnung"].astype(str).str.strip()
    df_weekly["richtung"] = df_weekly["richtung"].astype(str).str.strip()

    import unicodedata
    normalize = lambda s: unicodedata.normalize("NFC", s)

    df_daily["bezeichnung"] = df_daily["bezeichnung"].apply(normalize)
    df_daily["richtung"] = df_daily["richtung"].apply(normalize)
    df_weekly["bezeichnung"] = df_weekly["bezeichnung"].apply(normalize)
    df_weekly["richtung"] = df_weekly["richtung"].apply(normalize)

    # ----------------------------------------------------------------------
    # 3. Sort data and ensure numeric types
    # ----------------------------------------------------------------------
    df_daily = df_daily.sort_values(["bezeichnung", "richtung", "DATUM"])
    df_weekly = df_weekly.sort_values(["bezeichnung", "richtung", "DATUM"])

    df_daily["VELO"] = df_daily["VELO"].astype(float)
    df_weekly["VELO"] = df_weekly["VELO"].astype(float)

    df_daily["DATUM"] = pd.to_datetime(df_daily["DATUM"])
    df_weekly["DATUM"] = pd.to_datetime(df_weekly["DATUM"])

    # ----------------------------------------------------------------------
    # 4. Extract all station-direction pairs
    # ----------------------------------------------------------------------
    station_dir_pairs = (
        df_daily[["bezeichnung", "richtung"]]
        .drop_duplicates()
        .sort_values(["bezeichnung", "richtung"])
        .values.tolist()
    )

    # ----------------------------------------------------------------------
    # 5. Build a dictionary of all figures as JSON
    #    Key format: "station|direction|daily" or "station|direction|weekly"
    # ----------------------------------------------------------------------
    fig_dict = {}

    for station, direction in station_dir_pairs:

        # Filter slices
        ddf = df_daily[
            (df_daily["bezeichnung"] == station) &
            (df_daily["richtung"] == direction)
        ].copy()

        wdf = df_weekly[
            (df_weekly["bezeichnung"] == station) &
            (df_weekly["richtung"] == direction)
        ].copy()

        # Ensure sorted
        ddf = ddf.sort_values("DATUM")
        wdf = wdf.sort_values("DATUM")

        # Convert DATUM to ISO strings (robust for Plotly JSON)
        #ddf["DATUM_STR"] = ddf["DATUM"].dt.strftime("%Y-%m-%d")
        ddf["X"] = ddf["DATUM"]  # keep as datetime64

        wdf["DATUM_STR"] = wdf["DATUM"].dt.strftime("%Y-%m-%d")


        ddf = ddf.copy()
        ddf["X"] = ddf["DATUM"].dt.strftime("%Y-%m-%d")

        wdf = wdf.copy()
        wdf["X"] = wdf["DATUM"].dt.strftime("%Y-%m-%d")

        # print(ddf[["DATUM", "VELO"]].head(20))
        # print(ddf[["DATUM", "VELO"]].tail(20))
        # print("Unique VELO:", ddf["VELO"].nunique())
        # print("Unique DATUM:", ddf["DATUM"].nunique())

        print("=== OUTER LOOP DATA ===")
        print(ddf["X"].apply(lambda s: [ord(c) for c in s]).head())

        print("Station:", station)
        print("Direction:", direction)
        print("First 10 DATUM:", df_daily["DATUM"].head(10).tolist())
        print("First 10 VELO:", df_daily["VELO"].head(10).tolist())


        # Create figures
        
        fig_daily = make_daily_plot(ddf, station, direction)
        fig_weekly = make_weekly_plot(wdf, station, direction)


        # Convert to JSON once
        daily_json = json.loads(fig_daily.to_json())
        weekly_json = json.loads(fig_weekly.to_json())

        # Store in dictionary
        fig_dict[f"{station}|{direction}|daily"] = daily_json
        fig_dict[f"{station}|{direction}|weekly"] = weekly_json




    # ----------------------------------------------------------------------
    # 6. Build dropdown options
    # ----------------------------------------------------------------------
    stations = sorted({s for s, _ in station_dir_pairs})
    station_options = "".join(f'<option value="{s}">{s}</option>' for s in stations)

    # JSON for JS
    figures_json = json.dumps(fig_dict)




    # ----------------------------------------------------------------------
    # 7. Build final HTML (single plot container)
    # ----------------------------------------------------------------------
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{page_title}</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>

<style>
body {{
    font-family: system-ui, sans-serif;
    margin: 20px;
}}
.controls {{
    margin-bottom: 20px;
}}
select {{
    padding: 6px;
    margin-right: 10px;
}}
</style>
</head>

<body>

<h1>{page_title}</h1>

<div class="controls">
    <label>Station:</label>
    <select id="stationSelect">{station_options}</select>

    <label>Direction:</label>
    <select id="directionSelect"></select>

    <label>Aggregation:</label>
    <select id="aggSelect">
        <option value="daily">Daily</option>
        <option value="weekly">Weekly</option>
    </select>
</div>

<div id="plotContainer"></div>

<script>
// All figures as JSON
const FIGURES = {figures_json};

// Populate direction dropdown based on station
function updateDirections() {{
    const station = document.getElementById("stationSelect").value;
    const dirSelect = document.getElementById("directionSelect");

    const dirs = Object.keys(FIGURES)
        .filter(k => k.startsWith(station + "|"))
        .map(k => k.split("|")[1]);

    const uniqueDirs = [...new Set(dirs)];

    dirSelect.innerHTML = "";
    uniqueDirs.forEach(d => {{
        const opt = document.createElement("option");
        opt.value = d;
        opt.textContent = d;
        dirSelect.appendChild(opt);
    }});

    updatePlot();
}}

// Render selected plot
function updatePlot() {{
    const station = document.getElementById("stationSelect").value;
    const direction = document.getElementById("directionSelect").value;
    const agg = document.getElementById("aggSelect").value;

    const key = `${{station}}|${{direction}}|${{agg}}`;
    const fig = FIGURES[key];

    if (!fig) {{
        document.getElementById("plotContainer").innerHTML = "";
        return;
    }}

    Plotly.newPlot("plotContainer", fig.data, fig.layout, {{responsive: true}});
    Plotly.Plots.resize("plotContainer");

}}

document.getElementById("stationSelect").addEventListener("change", updateDirections);
document.getElementById("directionSelect").addEventListener("change", updatePlot);
document.getElementById("aggSelect").addEventListener("change", updatePlot);

window.onload = updateDirections;
</script>

</body>
</html>
"""

    # ----------------------------------------------------------------------
    # 8. Write and upload HTML
    # ----------------------------------------------------------------------
    html_local_path = os.path.join(output_dir, html_filename)
    with open(html_local_path, "w", encoding="utf-8") as f:
        f.write(html)

    s3_key = f"{s3_prefix}/{html_filename}"
    with open(html_local_path, "rb") as f:
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=f,
            ContentType="text/html",
            CacheControl="no-cache"
        )

    print(f"Interactive HTML uploaded to s3://{bucket}/{s3_key}")


def make_daily_plot(df, station, direction):
    print("=== PLOT FUNCTION DATA ===")
    print("Station:", station)
    print("Direction:", direction)
    print("First 10 X:", df["X"].head(10).tolist())
    print("First 10 VELO:", df["VELO"].head(10).tolist())
    print("X dtype:", df["X"].dtype)
    print("Unique types in X:", {type(x) for x in df["X"].head(20)})
    print(repr(df["X"].iloc[0]))
    print("VELO dtype:", df["VELO"].dtype)
    print("Unique types in VELO:", {type(v) for v in df["VELO"].head(20)})
    print("X head:", df["X"].head(10).tolist())
    print("Y head:", df["VELO"].head(10).tolist())
    print("Sorted by X:", df.sort_values("X")["VELO"].head(10).tolist())
    print("Sorted by DATUM:", df.sort_values("DATUM")["VELO"].head(10).tolist())
    print("Index:", df.index[:10].tolist())

    fig = go.Figure()
    fig.update_xaxes(type="date")

    fig.add_trace(go.Scatter(
        x=df["X"],
        y=df["VELO"],
        #mode="lines",
        mode="lines+markers"
    ))
    fig.update_xaxes(type="date")
    return fig


def make_weekly_plot(df, station, direction):
    print("=== WEEKLY PLOT FUNCTION DATA ===")
    print("Station:", station)
    print("Direction:", direction)
    print("First 10 X:", df["X"].head(10).tolist())
    print("First 10 VELO:", df["VELO"].head(10).tolist())

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["X"],
        y=df["VELO"],
        mode="lines"
    ))
    return fig


def make_daily_plot_oldold(df):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["DATUM"],
        y=df["VELO"],
        mode="lines",
        name="Daily"
    ))
    fig.update_layout(xaxis_title="Datum", yaxis_title="VELO")
    return fig



def make_daily_plot_old(df):
    """
    df: daily data for a single (bezeichnung, richtung)
        must contain columns: DATUM (datetime), VELO (numeric)
    """


    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="No data available",
            xaxis_title="Date",
            yaxis_title="Bikes per direction"
        )
        return fig
        


    name = df["bezeichnung"].iloc[0]
    direction = df["richtung"].iloc[0]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["DATUM"],
        y=df["VELO"],
        mode="lines+markers",
        name=f"{name} → {direction} (daily)"
    ))

    fig.update_layout(
        title=f"Bike Counts – {name} → {direction} (daily)",
        xaxis_title="Date",
        yaxis_title="Bikes per direction",
        template="plotly_white"
    )
    return fig




def make_weekly_plot_old(df):
    """
    df: weekly data for a single (bezeichnung, richtung)
        must contain columns: DATUM (week start or label), VELO (numeric)
    """
    if df["DATUM"].dtype != "datetime64[ns]":
        df = df.assign(DATUM=pd.to_datetime(df["DATUM"]))
    df = df.sort_values("DATUM")
 
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="No data available",
            xaxis_title="Week",
            yaxis_title="Bikes per direction"
        )
        return fig

    name = df["bezeichnung"].iloc[0]
    direction = df["richtung"].iloc[0]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["DATUM"],
        y=df["VELO"],
        name=f"{name} → {direction} (weekly)"
    ))

    fig.update_layout(
        title=f"Bike Counts – {name} → {direction} (weekly)",
        xaxis_title="Week",
        yaxis_title="Bikes per direction",
        template="plotly_white"
    )
    return fig
