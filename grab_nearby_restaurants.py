"""
近所の飲食店情報を SQLite DB に保存するスクリプト
"""

import os
import time
import math
import requests
import sqlite3
import logging
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 環境変数の読み込み
API_KEY  = os.getenv("GMAPS_API_KEY")
LOCATION = os.getenv("LOCATION")
RADIUS   = float(os.getenv("RADIUS", "500"))
TYPE     = os.getenv("TYPE", "restaurant")
LANG     = os.getenv("LANG", "ja")
DB_FILE  = os.getenv("DB_FILE", "restaurants.db")

if not API_KEY:
    raise RuntimeError("APIキーが設定されていません。環境変数 GMAPS_API_KEY を確認してください。")

def gmaps_get(url: str, params: dict):
    for i in range(3):
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            logging.warning(f"リクエスト失敗（{i+1}回目）: {e}")
            time.sleep(1)
    raise RuntimeError("Google API へのリクエストに3回失敗しました。")

def make_maps_url(place_id: str) -> str:
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

def move_location(lat, lng, d_north=0, d_east=0):
    d_lat = d_north / 111320
    d_lng = d_east / (111320 * math.cos(math.radians(lat)))
    return lat + d_lat, lng + d_lng

def fetch_places(location):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{location[0]},{location[1]}",
        "radius": int(RADIUS),
        "type": TYPE,
        "language": LANG,
        "key": API_KEY
    }

    all_results = []
    while True:
        data = gmaps_get(url, params)
        all_results.extend(data.get("results", []))
        token = data.get("next_page_token")
        if not token:
            break
        time.sleep(2)
        params = {"pagetoken": token, "key": API_KEY}
    return all_results

def save_to_db(places):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS restaurants (
            place_id TEXT PRIMARY KEY,
            name TEXT,
            address TEXT,
            lat REAL,
            lng REAL,
            rating REAL,
            maps_url TEXT,
            last_visited TEXT,
            hidden INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for p in places:
        try:
            pid = p.get("place_id")
            name = p.get("name")
            addr = p.get("vicinity")
            lat  = p["geometry"]["location"]["lat"]
            lng  = p["geometry"]["location"]["lng"]
            rating = p.get("rating")
            url  = make_maps_url(pid)
            cur.execute("""
                INSERT INTO restaurants (place_id, name, address, lat, lng, rating, maps_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(place_id) DO UPDATE SET
                    rating=excluded.rating,
                    updated_at=CURRENT_TIMESTAMP
            """, (pid, name, addr, lat, lng, rating, url))
        except Exception as e:
            logging.warning(f"保存中にエラー: {e}")
    conn.commit()
    conn.close()

def main():
    base_lat, base_lng = map(float, LOCATION.split(","))
    offsets = [
        (0, 0),
        (RADIUS, 0), (-RADIUS, 0),
        (0, RADIUS), (0, -RADIUS),
    ]
    all_places = []
    for d_north, d_east in offsets:
        lat, lng = move_location(base_lat, base_lng, d_north, d_east)
        logging.info(f"取得中: {lat:.6f},{lng:.6f}")
        places = fetch_places((lat, lng))
        all_places.extend(places)

    unique = {p["place_id"]: p for p in all_places}.values()
    save_to_db(unique)
    logging.info(f"{len(unique)} 件を {DB_FILE} に保存しました。")

if __name__ == "__main__":
    main()
