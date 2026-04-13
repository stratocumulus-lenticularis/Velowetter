import os
import json
import re
import boto3
import pandas as pd


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]+", "", text)
    return text


def plot_and_upload_interactive(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    output_dir: str,
    bucket: str,
    s3_prefix: str,
    page_title: str = "Bike Counts – Interactive",
    html_filename: str = "index.html"
):
    os.makedirs(output_dir, exist_ok=True)
    s3 = boto3.client("s3")

    station_dir_pairs = (
        df_daily[["bezeichnung", "richtung"]]
        .drop_duplicates()
        .sort_values(["bezeichnung", "richtung"])
        .values.tolist()
    )

    data_dict = {}
    for station, direction in station_dir_pairs:
        ddf = df_daily[
            (df_daily["bezeichnung"] == station) &
            (df_daily["richtung"] == direction)
        ].sort_values("DATUM")

        wdf = df_weekly[
            (df_weekly["bezeichnung"] == station) &
            (df_weekly["richtung"] == direction)
        ].sort_values("DATUM")

        data_dict[f"{station}|{direction}|daily"] = {
            "x": ddf["DATUM"].dt.strftime("%Y-%m-%d").tolist(),
            "y": ddf["VELO"].tolist(),
            "trend": ddf["VELO_TREND"].tolist() if "VELO_TREND" in ddf.columns else None
        }
        data_dict[f"{station}|{direction}|weekly"] = {
            "x": wdf["DATUM"].dt.strftime("%Y-%m-%d").tolist(),
            "y": wdf["VELO"].tolist(),
            "trend": wdf["VELO_TREND"].tolist() if "VELO_TREND" in wdf.columns else None
        }

    stations = sorted({s for s, _ in station_dir_pairs})
    station_options = "".join(f'<option value="{s}">{s}</option>' for s in stations)
    figures_json = json.dumps(data_dict)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{page_title}</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
body {{ font-family: system-ui, sans-serif; margin: 20px; }}
.controls {{ margin-bottom: 20px; }}
select {{ padding: 6px; margin-right: 10px; }}
nav {{ margin-bottom: 18px; }}
nav a {{ margin-right: 14px; text-decoration: none; color: #3a6bc4; font-weight: 500; }}
nav a.active {{ color: #111; text-decoration: underline; cursor: default; pointer-events: none; }}
</style>
</head>
<body>
<nav>
  <a href="index.html" class="active">Detail view</a>
  <a href="overview.html">Overview</a>
</nav>
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
const FIGURES = {figures_json};

function updateDirections() {{
    const station = document.getElementById("stationSelect").value;
    const dirSelect = document.getElementById("directionSelect");
    const dirs = [...new Set(
        Object.keys(FIGURES)
            .filter(k => k.startsWith(station + "|"))
            .map(k => k.split("|")[1])
    )];
    dirSelect.innerHTML = dirs.map(d => `<option value="${{d}}">${{d}}</option>`).join("");
    updatePlot();
}}

function updatePlot() {{
    const station = document.getElementById("stationSelect").value;
    const direction = document.getElementById("directionSelect").value;
    const agg = document.getElementById("aggSelect").value;
    const d = FIGURES[`${{station}}|${{direction}}|${{agg}}`];
    if (!d) {{ document.getElementById("plotContainer").innerHTML = "<p>No data found</p>"; return; }}

    const traces = [
        {{
            x: d.x, y: d.y,
            type: "scatter", mode: "lines",
            name: "Observed",
            line: {{ color: "steelblue", width: 1 }},
            opacity: 0.6
        }}
    ];
    if (d.trend) {{
        traces.push({{
            x: d.x, y: d.trend,
            type: "scatter", mode: "lines",
            name: "Trend (1yr LOESS)",
            line: {{ color: "crimson", width: 2.5 }},
            connectgaps: false
        }});
    }}

    Plotly.newPlot("plotContainer", traces, {{
        xaxis: {{ type: "date", title: "Date" }},
        yaxis: {{ title: "Bikes" }},
        title: `${{station}} \u2192 ${{direction}} (${{agg}})`,
        legend: {{ orientation: "h", y: -0.15 }}
    }}, {{responsive: true}});
}}

document.getElementById("stationSelect").addEventListener("change", updateDirections);
document.getElementById("directionSelect").addEventListener("change", updatePlot);
document.getElementById("aggSelect").addEventListener("change", updatePlot);
window.onload = updateDirections;
</script>
</body>
</html>"""

    html_local_path = os.path.join(output_dir, html_filename)
    print(f"Writing HTML to: {os.path.abspath(html_local_path)}")
    with open(html_local_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Uploading {html_filename} to s3://{bucket}/{s3_prefix}/{html_filename} ...")
    s3_key = f"{s3_prefix}/{html_filename}"
    with open(html_local_path, "rb") as f:
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=f,
            ContentType="text/html",
            CacheControl="no-cache, no-store, must-revalidate"
        )
    print("Upload complete.")


def plot_and_upload_overview(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    output_dir: str,
    bucket: str,
    s3_prefix: str,
    page_title: str = "Bike Counts – Overview",
    html_filename: str = "overview.html"
):
    """
    Single plot with all (station, direction) LOESS trend lines overlaid,
    plus an aggregation toggle (daily / weekly).
    Raw series are toggled per-trace via the Plotly legend.
    """
    os.makedirs(output_dir, exist_ok=True)
    s3 = boto3.client("s3")

    station_dir_pairs = (
        df_daily[["bezeichnung", "richtung"]]
        .drop_duplicates()
        .sort_values(["bezeichnung", "richtung"])
        .values.tolist()
    )

    # Build a compact data structure: { "station|direction": { daily: {x,y,trend}, weekly: ... } }
    overview: dict = {}
    for station, direction in station_dir_pairs:
        key = f"{station}|{direction}"
        overview[key] = {}
        for agg_label, df in (("daily", df_daily), ("weekly", df_weekly)):
            sub = df[
                (df["bezeichnung"] == station) &
                (df["richtung"] == direction)
            ].sort_values("DATUM")
            overview[key][agg_label] = {
                "x":     sub["DATUM"].dt.strftime("%Y-%m-%d").tolist(),
                "y":     sub["VELO"].tolist(),
                "trend": sub["VELO_TREND"].tolist() if "VELO_TREND" in sub.columns else [],
            }

    overview_json = json.dumps(overview)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{page_title}</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 20px; }}
  .controls {{ margin-bottom: 16px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }}
  label {{ font-weight: 500; }}
  select {{ padding: 5px 8px; }}
  .toggle-group {{ display: flex; gap: 6px; }}
  .toggle-group button {{
      padding: 5px 14px; border: 1px solid #aaa; border-radius: 4px;
      background: #f5f5f5; cursor: pointer; font-size: 0.9rem;
  }}
  .toggle-group button.active {{
      background: #3a6bc4; color: #fff; border-color: #3a6bc4;
  }}
  nav {{ margin-bottom: 18px; }}
  nav a {{ margin-right: 14px; text-decoration: none; color: #3a6bc4; font-weight: 500; }}
  nav a.active {{ color: #111; text-decoration: underline; cursor: default; pointer-events: none; }}
</style>
</head>
<body>
<nav>
  <a href="index.html">Detail view</a>
  <a href="overview.html" class="active">Overview</a>
</nav>
<h1>{page_title}</h1>
<div class="controls">
  <div>
    <label>Aggregation:&nbsp;</label>
    <div class="toggle-group">
      <button id="btnDaily"  class="active" onclick="setAgg('daily')">Daily</button>
      <button id="btnWeekly"          onclick="setAgg('weekly')">Weekly</button>
    </div>
  </div>
  <div>
    <label>Show:&nbsp;</label>
    <div class="toggle-group">
      <button id="btnTrend" class="active" onclick="toggleLayer('trend')">Trend</button>
      <button id="btnRaw"              onclick="toggleLayer('raw')">Raw</button>
      <button id="btnBoth"             onclick="toggleLayer('both')">Both</button>
    </div>
  </div>
</div>
<div id="plot"></div>

<script>
const DATA  = {overview_json};
const KEYS  = Object.keys(DATA);

// Colour palette – one colour per series, shared between raw + trend traces
const PALETTE = [
  "#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd",
  "#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf",
  "#aec7e8","#ffbb78","#98df8a","#ff9896","#c5b0d5",
  "#c49c94","#f7b6d2","#c7c7c7","#dbdb8d","#9edae5",
  "#393b79","#637939","#8c6d31","#843c39","#7b4173",
];

let currentAgg   = "daily";
let currentLayer = "trend";  // "trend" | "raw" | "both"

function buildTraces(agg, layer) {{
  const traces = [];
  KEYS.forEach((key, i) => {{
    const colour = PALETTE[i % PALETTE.length];
    const d = DATA[key][agg];
    const label = key.replace("|", " → ");

    if (layer === "raw" || layer === "both") {{
      traces.push({{
        x: d.x, y: d.y,
        type: "scatter", mode: "lines",
        name: label + " (raw)",
        legendgroup: key,
        showlegend: layer === "raw",
        line: {{ color: colour, width: 1 }},
        opacity: 0.35,
        hovertemplate: "%{{x}}<br>%{{y:.0f}} bikes<extra>" + label + " raw</extra>",
      }});
    }}

    if ((layer === "trend" || layer === "both") && d.trend && d.trend.length) {{
      traces.push({{
        x: d.x, y: d.trend,
        type: "scatter", mode: "lines",
        name: label,
        legendgroup: key,
        showlegend: true,
        line: {{ color: colour, width: 2.2 }},
        connectgaps: false,
        hovertemplate: "%{{x}}<br>%{{y:.0f}} bikes<extra>" + label + " trend</extra>",
      }});
    }}
  }});
  return traces;
}}

const LAYOUT = {{
  xaxis: {{ type: "date", title: "Date" }},
  yaxis: {{ title: "Bikes per day" }},
  legend: {{ orientation: "v", x: 1.01, y: 1, font: {{ size: 11 }} }},
  margin: {{ r: 220 }},
  hovermode: "x unified",
}};

function render() {{
  Plotly.react("plot", buildTraces(currentAgg, currentLayer), LAYOUT, {{responsive: true}});
}}

function setAgg(agg) {{
  currentAgg = agg;
  document.getElementById("btnDaily").classList.toggle("active",  agg === "daily");
  document.getElementById("btnWeekly").classList.toggle("active", agg === "weekly");
  render();
}}

function toggleLayer(layer) {{
  currentLayer = layer;
  document.getElementById("btnTrend").classList.toggle("active", layer === "trend");
  document.getElementById("btnRaw").classList.toggle("active",   layer === "raw");
  document.getElementById("btnBoth").classList.toggle("active",  layer === "both");
  render();
}}

window.onload = render;
</script>
</body>
</html>"""

    html_local_path = os.path.join(output_dir, html_filename)
    print(f"Writing overview HTML to: {os.path.abspath(html_local_path)}")
    with open(html_local_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Uploading {html_filename} to s3://{bucket}/{s3_prefix}/{html_filename} ...")
    s3_key = f"{s3_prefix}/{html_filename}"
    with open(html_local_path, "rb") as f:
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=f,
            ContentType="text/html",
            CacheControl="no-cache, no-store, must-revalidate"
        )
    print("Upload complete.")