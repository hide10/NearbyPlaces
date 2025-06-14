import os
import time
import math
import requests
import sqlite3
import logging
from itertools import product
from dotenv import load_dotenv
from typing import List, Dict, Any, Tuple

# .env 読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 環境変数の読み込み
API_KEY    = os.getenv("GMAPS_API_KEY")
LOCATION   = os.getenv("LOCATION")
RADIUS     = float(os.getenv("RADIUS", "500"))
TYPE       = os.getenv("TYPE", "restaurant")
LANG       = os.getenv("LANG", "ja")
DB_FILE    = os.getenv("DB_FILE", "restaurants.db")
ITERATIONS = int(os.getenv("ITERATIONS", "1"))

if not API_KEY:
    raise RuntimeError("APIキーが設定されていません。環境変数 GMAPS_API_KEY を確認してください。")

STEP = RADIUS * 0.75

def gmaps_get(url: str, params: dict) -> dict:
    """Google Maps API へのGETリクエスト（リトライ付き）"""
    for i in range(3):
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            logging.warning(f"リクエスト失敗（{i+1}回目）: {e}")
            time.sleep(1)
    raise RuntimeError("Google API へのリクエストに3回失敗しました。")

def move_location(lat: float, lng: float, dx_blocks: int, dy_blocks: int) -> Tuple[float, float]:
    """指定ブロック数だけ緯度経度を移動"""
    d_north = dy_blocks * STEP
    d_east  = dx_blocks * STEP
    d_lat = d_north / 111320
    d_lng = d_east / (111320 * math.cos(math.radians(lat)))
    return lat + d_lat, lng + d_lng

def fetch_places(lat: float, lng: float) -> List[Dict[str, Any]]:
    """指定位置の周辺施設を取得"""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": int(RADIUS),
        "type": TYPE,
        "language": LANG,
        "key": API_KEY
    }
    results = []
    while True:
        data = gmaps_get(url, params)
        results.extend(data.get("results", []))
        token = data.get("next_page_token")
        if not token:
            break
        time.sleep(2)
        params = {"pagetoken": token, "key": API_KEY}
    logging.info(f"  › {lat:.6f},{lng:.6f} → {len(results)} 件")
    if len(results) >= 60:
        logging.warning("  ＊ この地点で60件以上取得されました。取得漏れの可能性があります。")
    return results

def make_maps_url(place_id: str) -> str:
    """Google Maps のURL生成"""
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

def save_to_db(places: List[Dict[str, Any]]) -> None:
    """取得した施設情報をDBに保存"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS restaurants (
            place_id     TEXT PRIMARY KEY,
            name         TEXT,
            address      TEXT,
            lat          REAL,
            lng          REAL,
            rating       REAL,
            maps_url     TEXT,
            last_visited TEXT,
            hidden       INTEGER DEFAULT 0,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for p in places:
        try:
            pid    = p.get("place_id")
            name   = p.get("name")
            addr   = p.get("vicinity")
            lat    = p["geometry"]["location"]["lat"]
            lng    = p["geometry"]["location"]["lng"]
            rating = p.get("rating")
            url    = make_maps_url(pid)
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

def get_offsets(base_lat: float, base_lng: float, iterations: int) -> List[Tuple[int, int]]:
    """中心からのオフセットリストを生成"""
    return [
        (dx, dy)
        for dx, dy in product(range(-iterations, iterations + 1), repeat=2)
        if abs(dx) + abs(dy) <= iterations
    ]

def main():
    base_lat, base_lng = map(float, LOCATION.split(","))
    offsets = get_offsets(base_lat, base_lng, ITERATIONS)

    logging.info(f"取得ブロック数: {len(offsets)} (ITERATIONS={ITERATIONS}, RADIUS={RADIUS}m)")

    all_places = []
    for dx, dy in offsets:
        lat, lng = move_location(base_lat, base_lng, dx, dy)
        logging.info(f"[Block dx={dx}, dy={dy}]")
        places = fetch_places(lat, lng)
        all_places.extend(places)

    unique = {p["place_id"]: p for p in all_places}.values()
    save_to_db(list(unique))

    logging.info(f"総ユニーク件数: {len(unique)} 件を {DB_FILE} に保存しました。")

if __name__ == "__main__":
    main()
