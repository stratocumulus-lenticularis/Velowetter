import datetime
import boto3
from pathlib import Path


s3 = boto3.client("s3")
bucket = "velowetter-site-mark"

OUTPUT_DIR = Path("output")

mime = { 
   ".html": "text/html", 
   ".css": "text/css", 
   ".js": "application/javascript", 
   ".png": "image/png", 
   ".jpg": "image/jpeg", 
}


def main():
   OUTPUT_DIR.mkdir(exist_ok=True)
   generated_files = ["index.html"]
   now = datetime.datetime.now(datetime.UTC).isoformat()

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

 # Example: add more files later
 # (OUTPUT_DIR / "style.css").write_text("body { font-family: sans-serif; }")
 # --- Upload everything in the directory ---

   for path in OUTPUT_DIR.iterdir():
     if path.is_file():
       ext = path.suffix
       content_type = mime.get(ext, "binary/octet-stream")
       print(f"Uploading {path.name} with Content-Type={content_type}")

       s3.upload_file(
         str(path),
         bucket,
         path.name, # S3 key
         ExtraArgs={"ContentType": content_type}
 )


if __name__ == "__main__":
    main()
