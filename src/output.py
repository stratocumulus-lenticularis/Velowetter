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

    # Build compact data dict for JS
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
            "y": ddf["VELO"].tolist()
        }
        data_dict[f"{station}|{direction}|weekly"] = {
            "x": wdf["DATUM"].dt.strftime("%Y-%m-%d").tolist(),
            "y": wdf["VELO"].tolist()
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
    Plotly.newPlot("plotContainer", [{{
        x: d.x, y: d.y, type: "scatter", mode: "lines"
    }}], {{
        xaxis: {{ type: "date", title: "Date" }},
        yaxis: {{ title: "Bikes" }},
        title: `${{station}} → ${{direction}} (${{agg}})`
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
    
    
    
    
