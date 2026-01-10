#run with 
# source /home/ubuntu/velowetter-env/bin/activate
# python main.py
from src.fetch import fetch_data
#from src.process import load_bike_counts, compute_daily_stats
#from src.visualize import plot_daily_counts
#from src.publish import upload_output

def run():
    fetch_data(dynamic=True,static=False)
    
 #   df = load_bike_counts()
 #   stats = compute_daily_stats(df)
 #   plot_daily_counts(stats)
 #   upload_output()

if __name__ == "__main__":
    run()
