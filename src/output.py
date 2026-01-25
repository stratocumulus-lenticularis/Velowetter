import matplotlib.pyplot as plt
import pandas as pd
import boto3

def save_and_upload_plot(df: pd.DataFrame,local_path: str, bucket: str, s3_key: str):
    
    """
    Create a time-series plot of VELO_IN + VELO_OUT
    for all selected FK_STANDORT stations.
    """

    # Ensure DATUM is datetime
    df["DATUM"] = pd.to_datetime(df["DATUM"])

    # Create a total count column
    df["TOTAL"] = df["VELO_IN"].fillna(0) + df["VELO_OUT"].fillna(0)

    # Group by station
    stations = df["FK_STANDORT"].unique()

    plt.figure(figsize=(14, 7))

    for station in stations:
        sub = df[df["FK_STANDORT"] == station].sort_values("DATUM")
        plt.plot(sub["DATUM"], sub["TOTAL"], label=f"Station {station}")

    plt.title("Bike Counts Over Time")
    plt.xlabel("Date")
    plt.ylabel("Total Bikes (In + Out)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()
    # Save to file 
    plt.savefig(local_path, dpi=150) 
    plt.close()
    
    # Upload to S3 
    s3 = boto3.client("s3") 
    s3.upload_file(local_path, bucket, s3_key) 
    print(f"Plot saved to {local_path}") 
    print(f"Plot uploaded to s3://{bucket}/{s3_key}")
     