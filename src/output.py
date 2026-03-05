import os
import matplotlib.pyplot as plt
import pandas as pd
import boto3
import re
import gc


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]+", "", text)
    return text


def plot_and_upload_plot(
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



