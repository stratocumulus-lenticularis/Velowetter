import datetime
from pathlib import Path

OUTPUT_DIR = Path("output")

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    now = datetime.datetime.utcnow().isoformat()

    html = f"""
    <html>
    <head><title>Velowetter Report</title></head>
    <body>
        <h1>Velowetter Report</h1>
        <p>Generated at: {now} UTC</p>
        <p>This is the first version of your automated report.</p>
    </body>
    </html>
    """

    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")

if __name__ == "__main__":
    main()
