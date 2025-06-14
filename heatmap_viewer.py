from flask import Flask, render_template
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

@app.route("/")
def index():
    db = os.getenv("DB_FILE", "restaurants.db")
    location_str = os.getenv("LOCATION", "35.681236,139.767125")
    radius = float(os.getenv("RADIUS", "500"))
    base_lat, base_lng = map(float, location_str.split(","))

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT lat, lng, SUM(count) as count FROM fetch_logs GROUP BY lat, lng")
    data = [{"lat": row["lat"], "lng": row["lng"], "count": row["count"]} for row in c.fetchall()]
    conn.close()

    return render_template(
        "heatmap.html",
        heatmap_data=data,
        base_lat=base_lat,
        base_lng=base_lng,
        api_key=os.getenv("GMAPS_API_KEY"),
        radius=radius
    )

if __name__ == "__main__":
    app.run(debug=True)
