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
# 複数タイプをカンマ区切り(またはセミコロン区切り)で指定可能にする
_types_env = os.getenv("TYPE", "restaurant").replace(";", ",")
TYPES      = [t.strip() for t in _types_env.split(",") if t.strip()]
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

def fetch_places(lat: float, lng: float, place_type: str) -> List[Dict[str, Any]]:
    """指定位置の周辺施設を取得"""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": int(RADIUS),
        "type": place_type,
        "language": LANG,
        "key": API_KEY
    }
    results = []
    while True:
        data = gmaps_get(url, params)
        batch = data.get("results", [])
        for r in batch:
            r["search_type"] = place_type
        results.extend(batch)
        token = data.get("next_page_token")
        if not token:
            break
        time.sleep(2)
        params = {"pagetoken": token, "key": API_KEY}
    logging.info(f"  › {lat:.6f},{lng:.6f} [{place_type}] → {len(results)} 件")
    if len(results) >= 60:
        logging.warning("  ＊ この地点で60件以上取得されました。取得漏れの可能性があります。")
    return results

def make_maps_url(place_id: str) -> str:
    """Google Maps のURL生成"""
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

def fetch_drive_time(dest_lat: float, dest_lng: float) -> int | None:
    """指定地点まで車で移動した際の所要時間(秒)を取得"""
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": LOCATION,
        "destinations": f"{dest_lat},{dest_lng}",
        "mode": "driving",
        "language": LANG,
        "key": API_KEY,
    }
    try:
        data = gmaps_get(url, params)
        if data.get("status") != "OK":
            logging.warning(f"Distance Matrix status: {data.get('status')}")
            return None
        element = data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            logging.warning(f"Element status: {element.get('status')}")
            return None
        return element.get("duration", {}).get("value")
    except Exception as e:
        logging.warning(f"距離計算に失敗: {e}")
        return None

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
            drive_time   INTEGER,
            type         TEXT,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 既存DBにカラムが無い場合は追加
    cur.execute("PRAGMA table_info(restaurants)")
    cols = [r[1] for r in cur.fetchall()]
    if "drive_time" not in cols:
        cur.execute("ALTER TABLE restaurants ADD COLUMN drive_time INTEGER")
    if "type" not in cols:
        cur.execute("ALTER TABLE restaurants ADD COLUMN type TEXT")

    for p in places:
        try:
            pid    = p.get("place_id")
            name   = p.get("name")
            addr   = p.get("vicinity")
            lat    = p["geometry"]["location"]["lat"]
            lng    = p["geometry"]["location"]["lng"]
            rating = p.get("rating")
            url    = make_maps_url(pid)
            drive  = fetch_drive_time(lat, lng)
            time.sleep(0.1)  # API使用量を抑える
            ptype  = p.get("search_type")
            cur.execute(
                """
                INSERT INTO restaurants (
                    place_id, name, address, lat, lng, rating, maps_url, drive_time, type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(place_id) DO UPDATE SET
                    rating=excluded.rating,
                    drive_time=excluded.drive_time,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (pid, name, addr, lat, lng, rating, url, drive, ptype),
            )
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
        for t in TYPES:
            logging.info(f"[Block dx={dx}, dy={dy}, type={t}]")
            places = fetch_places(lat, lng, t)
            all_places.extend(places)

    unique = {}
    for p in all_places:
        if p["place_id"] not in unique:
            unique[p["place_id"]] = p

    save_to_db(list(unique.values()))

    logging.info(f"総ユニーク件数: {len(unique)} 件を {DB_FILE} に保存しました。")

if __name__ == "__main__":
    main()
