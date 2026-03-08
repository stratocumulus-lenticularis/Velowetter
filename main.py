#run with 
# source /home/ubuntu/velowetter-env/bin/activate
# python main.py
import os 
import yaml
import pandas as pd

from src.fetch import fetch_data
import src.load_data as ld 
import src.load_metadata as lmd 
import src.output as out 
import src.data_aggregation as da

#from src.process import load_bike_counts, compute_daily_stats
#from src.visualize import plot_daily_counts
#from src.publish import upload_output

import unicodedata

def normalize(s):
    return unicodedata.normalize("NFC", s)


def run():
    # choose stations by name 
    # 2) Define multiple Standort/direction pairs
    stations = [
        ("Bucheggplatz", "Höngg"),
#        ("Hofwiesenstrasse", "Bucheggplatz"),
        ("Bucheggplatz","Hofwiesenstrasse"),
 #       ("Schulstrasse", "Bahnhof Oerlikon"),
        ("Lux-Guyer-Weg", "Wipkingen"),
        ("Lux-Guyer-Weg", "Innenstadt")
    ]
    
    with open("config.yaml", "r") as f: 
        config = yaml.safe_load(f)

    bucket = config["aws"]["bucket"]
    s3_prefix = config["aws"]["s3_prefix"]
    output_dir = config["output"]["local_output_dir"]
    station_standorte_file = config["data_sources"]["stations"]
    
    # 1) Load metadata and build mapping
    meta = lmd.load_station_metadata(station_standorte_file)
    mapping = lmd.build_station_mapping_both_directions(meta)

    lmd.print_station_mapping(mapping)

    #for potential loops over stations and directions
    station_direction_list = lmd.get_all_station_directions(mapping)
    station_direction_list = stations
    #print(station_direction_list)
    
    #get ids of chosen stations
    # 3) Get all FK_STANDORT IDs for all these pairs 
    #fk_ids = lmd.get_fk_standort_for_multiple(mapping, stations)
    
    #collect all aggregated data here
    all_agg  = [] 
    
    for (station, direction) in station_direction_list:
        print(f"processing {station} -> {direction}")
        
        fk_ids = mapping.get((station, direction), [])
        if not fk_ids: 
            print(f" No FK_STANDORT IDs for {station} → {direction}, skipping.") 
            continue
        print(" Selected FK_STANDORT IDs:", fk_ids)

        # Load only the data for these IDs
        counts = ld.load_bike_data("config.yaml", fk_ids)
        if counts.empty:
            print(f" No data for {station} → {direction}, skipping.")
            continue
            
        # Merge with metadata
        merged = ld.merge_counts_with_metadata(counts, meta)
        

        # Convert VELO_IN / VELO_OUT into long format with correct directions
        long_df = da.wide_to_long_directional(merged)
        # Keep only needed columns
        all_agg.append(long_df)
        
        #all_agg.append(merged)
        
        del counts, merged, long_df
        
    # --- Combine everything into one DataFrame ---
    if not all_agg: 
         print("No data loaded.") 
         return
        
        
    full_df = pd.concat(all_agg, ignore_index=True)
    print("Full dataset shape:", full_df.shape)
    
    # --- Aggregate globally ---
    #agg = ld.aggregate_by_station_direction(full_df)
    agg = (
    full_df.groupby(["bezeichnung", "richtung", "DATUM"], as_index=False)["VELO"]
           .sum()
    )

    
    print("aggregated")
    
    # 7 aggregate to daily and weekly sums
    daily = da.make_daily_sums(agg)
    
    print("daily done")
    weekly = da.make_weekly_sums(agg)
    print("weekly done")   
    
    daily["DATUM"] = pd.to_datetime(daily["DATUM"], errors="coerce")
    weekly["DATUM"] = pd.to_datetime(weekly["DATUM"], errors="coerce")

    daily = daily.sort_values(["bezeichnung", "richtung", "DATUM"])
    weekly = weekly.sort_values(["bezeichnung", "richtung", "DATUM"])
    

    # out.plot_and_upload_plot( 
        # weekly, 
        # output_dir=output_dir, 
        # bucket=bucket, 
        # s3_prefix=s3_prefix 
    # )
    
    del agg
    out.plot_and_upload_interactive(
        df_daily=daily,
        df_weekly=weekly,
        make_daily_plot=out.make_daily_plot,
        make_weekly_plot=out.make_weekly_plot,
        output_dir=output_dir,
        bucket=bucket,
        s3_prefix=s3_prefix,
        html_filename="index.html"
    )




def dummy():
    # get all FK_STANDORT IDs (old + current) 
    #stations = ld.get_fk_standort(mapping, station_names)
    #stations = get_current_station_ids(meta, station_names)
    #print(stations)
    
    
    ####download new files from www
    #fetch_data(dynamic=True,static=False)
    
    # 4) Load all corresponding instruments   
    counts = ld.load_bike_data("config.yaml", fk_ids)
    
    print("\nLoaded data shape:", counts.shape)
    #print(counts.head())
    
    # 5) Attach bezeichnung + richtung_out 
    merged = ld.merge_counts_with_metadata(counts, meta)
    # Schritt 1: gemeinsames Richtungsfeld erzeugen
   

    # Variante mit Duplikation: jede Messung bekommt zwei Richtungen
    rows_out = merged.copy()
    rows_out["richtung"] = rows_out["richtung_out"]

    rows_in = merged.copy()
    rows_in["richtung"] = rows_in["richtung_in"]

    merged_both = pd.concat([rows_out, rows_in], ignore_index=True)

    # Ungültige Richtungen (NaN / leere Strings) rauswerfen
    merged_both = merged_both[merged_both["richtung"].notna() & (merged_both["richtung"] != "")]

    #print(merged_both["richtung"].unique())
    #print(merged_both[merged_both["bezeichnung"] == "Lux-Guyer-Weg"]["richtung"].unique())

   
    
    # 6) Aggregate per Standort/direction/time 
    agg = ld.aggregate_by_station_direction(merged_both)
    
    #print(agg.head())

    
    # 7 aggregate to daily and weekly sums
    daily = da.make_daily_sums(agg)
    #weekly = da.make_weekly_sums(agg)

    
 #   df = load_bike_counts()
 #   stats = compute_daily_stats(df)
 #   plot_daily_counts(stats)
 #   upload_output()
 
    out.plot_and_upload_plot( 
        daily, 
        output_dir=output_dir, 
        bucket=bucket, 
        s3_prefix=s3_prefix 
    )
    
    
    

if __name__ == "__main__":
    run()
