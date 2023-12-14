from flask import Flask, render_template,request,redirect, url_for

from dotenv import load_dotenv
import os
from haversine import haversine, Unit
import pandas as pd
import requests

load_dotenv()

app = Flask(__name__, template_folder="html")

key = os.getenv('GMAP_KEY')
data_path = os.getenv('DATA_PATH')

df = pd.read_csv(data_path)
    
public_stations = df[df['Groups With Access Code'].str.contains('Public', na=False)]
public_stations = public_stations[['Station Name', 'Address', 'Latitude','Longitude','EV Connector Types']]      

def convert_seconds_to_hms(seconds):
  hours = seconds // 3600
  seconds %= 3600
  minutes = seconds // 60
  seconds %= 60

  if hours > 0:
    return f"{hours:.0f} hr {minutes:.0f} min"
  elif minutes > 0:
    return f"{minutes:.0f} min"
  else:
    return f"1 min"

def meters_to_miles(meters):
  miles = meters / 1609.34
  return miles

@app.route("/")
def home():
    return render_template("index.html", key=key)

@app.route("/find", methods=['POST'])
def find():
    if request.method == 'POST':
        
        s_lng = request.form["lng"]
        s_lat = request.form["lat"]

        # Example user input for their current location (s_lat, s_lng)
        user_location = (float(s_lat), float(s_lng))  # Example: Downtown Los Angeles, CA

        # Function to calculate distance between two points
        def calculate_distance(user_loc, station_loc):
            return haversine(user_loc, station_loc, unit=Unit.MILES)

        # Add a new column 'Distance' to the dataframe by applying the calculate_distance function
        public_stations['Distance'] = public_stations.apply(
            lambda row: calculate_distance(user_location, (row['Latitude'], row['Longitude'])), axis=1
        )

        # Sort the dataframe by the new 'Distance' column to find the nearest station
        nearest_stations = public_stations.sort_values(by='Distance')

        res = nearest_stations.head(5)
        res = res.reset_index(drop=True)

        lat_lng_list = res[['Latitude', 'Longitude']].itertuples(index=False, name=None)

        q_string = ';'.join([f"{lng},{lat}" for lat, lng in lat_lng_list])
        url = f"http://router.project-osrm.org/table/v1/driving/{float(s_lng)},{float(s_lat)};{q_string}?sources=0&annotations=duration,distance"

        r = requests.get(url)
        response = r.json()
        res['Duration'] = response['durations'][0][1:]
        res['Distance'] = response['distances'][0][1:]
        res = res.sort_values(by="Duration").reset_index(drop=True)

        res["Duration"] = res["Duration"].apply(lambda dur:convert_seconds_to_hms(dur))
        res["Distance"] = res["Distance"].apply(lambda dis:f"{round(meters_to_miles(dis),2)} miles")
        res["URL"] = res.apply(lambda row: f"https://www.google.com/maps/dir/?api=1&origin={float(s_lat)},{float(s_lng)}&destination={row["Latitude"]},{row["Longitude"]}&travelmode=driving&dir_action=navigate",axis=1)
        res = res.drop(columns=['Latitude', 'Longitude'])
        stations = res.to_dict(orient='records')

        return render_template("find.html",stations=stations)    
    else:
        return render_template("index.html", key=key)

@app.errorhandler(404)
def page_not_found(e):
    
    return redirect(url_for('home'))

@app.errorhandler(405)
def method_not_allowed(e):
    
    return redirect(url_for('home'))

# run the app
if __name__ == "__main__":
    app.run()