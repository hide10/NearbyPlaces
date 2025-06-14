import sqlite3
import folium
from folium.plugins import HeatMap
import os
from dotenv import load_dotenv

load_dotenv()

# .envから中心座標を取得
location_str = os.getenv("LOCATION", "35.681236,139.767125")
base_lat, base_lng = map(float, location_str.split(","))

# DBから全店舗の座標を取得
conn = sqlite3.connect('restaurants.db')
cursor = conn.cursor()
cursor.execute("SELECT lat, lng FROM restaurants")
locations = cursor.fetchall()
conn.close()

# ヒートマップ作成
m = folium.Map(location=[base_lat, base_lng], zoom_start=12)
HeatMap(locations).add_to(m)
m.save('heatmap.html')

print("ヒートマップを heatmap.html に保存しました。")
