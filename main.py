#run with 
# source /home/ubuntu/velowetter-env/bin/activate
# python main.py
from src.fetch import fetch_data
import src.load_data as ld 
import src.load_metadata as lmd 
import src.output as out 

#from src.process import load_bike_counts, compute_daily_stats
#from src.visualize import plot_daily_counts
#from src.publish import upload_output

def run():
    # choose stations by name 
    stations = [
        ("Bucheggplatz", "Höngg"),
        ("Schulstrasse", "Bahnhof Oerlikon"),
        ("Lux-Guyer-Weg", "Wipkingen"),
    ]

    
    
    # map to FK_STANDORT 
    meta = lmd.load_station_metadata("data/taz.view_eco_standorte.csv")
    mapping = lmd.build_station_mapping_by_out(meta)

    lmd.print_station_mapping(mapping)
    
    #get ids of chosen stations
    fk_ids = lmd.get_fk_standort_for_multiple(mapping, stations)
    print("\nSelected FK_STANDORT IDs:", fk_ids)

    # get all FK_STANDORT IDs (old + current) 
    #stations = ld.get_fk_standort(mapping, station_names)
    #stations = get_current_station_ids(meta, station_names)
    #print(stations)
    
    
    #download new files from www
    #fetch_data(dynamic=True,static=False)
    
        
    df = ld.load_bike_data("config.yaml", fk_ids)
    
    print("\nLoaded data shape:", df.shape)
    print(df.head())
    
    
    
 #   df = load_bike_counts()
 #   stats = compute_daily_stats(df)
 #   plot_daily_counts(stats)
 #   upload_output()
 
    out.save_and_upload_plot( 
        df, 
        local_path="bike_timeseries.png", 
        bucket="velowetter-site-mark", 
        s3_key="plots/bike_timeseries.png" 
    )
    
    
    

if __name__ == "__main__":
    run()
