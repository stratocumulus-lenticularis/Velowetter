#run with 
# source /home/ubuntu/velowetter-env/bin/activate
# python main.py
import pandas as pd

from src.fetch import fetch_data
import src.load_data as ld 
import src.load_metadata as lmd 
import src.output as out 
import src.data_aggregation as da

#from src.process import load_bike_counts, compute_daily_stats
#from src.visualize import plot_daily_counts
#from src.publish import upload_output

def run():
    # choose stations by name 
    # 2) Define multiple Standort/direction pairs
    stations = [
        #("Bucheggplatz", "Höngg"),
        ("Hofwiesenstrasse", "Bucheggplatz"),
        ("Bucheggplatz","Hofwiesenstrasse"),
        ("Schulstrasse", "Bahnhof Oerlikon"),
        ("Lux-Guyer-Weg", "Wipkingen"),
        ("Lux-Guyer-Weg", "Innenstadt")
    ]

    
    
    # 1) Load metadata and build mapping
    meta = lmd.load_station_metadata("data/taz.view_eco_standorte.csv")
    mapping = lmd.build_station_mapping_both_directions(meta)

    lmd.print_station_mapping(mapping)
    
    #get ids of chosen stations
    # 3) Get all FK_STANDORT IDs for all these pairs 
    fk_ids = lmd.get_fk_standort_for_multiple(mapping, stations)
    
    print("\nSelected FK_STANDORT IDs:", fk_ids)

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
        output_dir="output/", 
        bucket="velowetter-site-mark", 
        s3_prefix="plots" 
    )
    
    
    

if __name__ == "__main__":
    run()
