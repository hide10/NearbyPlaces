"""
近所の飲食店情報を SQLite DB に保存するスクリプト
取得範囲を“中心点から半径 R だけ移動したブロック”で繰り返し取得できるように拡張。
ITERATIONS=1 → 中心+四方の1ブロック（合計5地点）
ITERATIONS=2 → 添付画像の 1〜13 のように、縦横2ブロックまでをカバー（合計25地点）
"""

import os
import time
import math
import requests
import sqlite3
import logging
from itertools import product
from dotenv import load_dotenv

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

# ブロック間の移動ステップ（75%重ねて取得範囲の抜けを防ぐ）
STEP = RADIUS * 0.75

def gmaps_get(url: str, params: dict):
    """最大3回のリトライ付きで JSON を返す"""
    for i in range(3):
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            logging.warning(f"リクエスト失敗（{i+1}回目）: {e}")
            time.sleep(1)
    raise RuntimeError("Google API へのリクエストに3回失敗しました。")

# ---------------- 位置計算 ----------------

def move_location(lat: float, lng: float, dx_blocks: int, dy_blocks: int):
    """ブロック単位のオフセットを緯度経度に変換"""
    d_north = dy_blocks * STEP  # +y は北（緯度正方向）
    d_east  = dx_blocks * STEP  # +x は東（経度正方向）
    d_lat = d_north / 111320
    d_lng = d_east / (111320 * math.cos(math.radians(lat)))
    return lat + d_lat, lng + d_lng

def fetch_places(lat: float, lng: float):
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
        logging.warning("  ※ この地点で60件以上取得されました。取得漏れの可能性があります。RADIUSやSTEPを見直してください。")
    return results

def make_maps_url(place_id: str) -> str:
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

def save_to_db(places, heatmap_points):
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fetch_logs (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            lat    REAL,
            lng    REAL,
            count  INTEGER,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

    for point in heatmap_points:
        try:
            logging.info(f"保存予定: lat={point['lat']}, lng={point['lng']}, count={point['count']}")
            cur.execute("INSERT INTO fetch_logs (lat, lng, count) VALUES (?, ?, ?)",
                        (point["lat"], point["lng"], point["count"]))
        except Exception as e:
            logging.warning(f"fetch_logs 保存エラー: {e}")

    conn.commit(); conn.close()

def main():
    base_lat, base_lng = map(float, LOCATION.split(","))

    # ブロックオフセット生成 (マンハッタン距離 <= ITERATIONS)
    offsets = [
        (dx, dy)
        for dy, dx in product(range(-ITERATIONS, ITERATIONS + 1), repeat=2)
        if max(abs(dx), abs(dy)) <= ITERATIONS
    ]
    # 中心からの距離でソートして“スパイラル”順に取得（見た目重視）
    offsets.sort(key=lambda t: (abs(t[0]) + abs(t[1]), t[1], t[0]))

    logging.info(f"取得ブロック数: {len(offsets)} (ITERATIONS={ITERATIONS}, RADIUS={RADIUS}m)")

    all_places = []
    heatmap_points = []
    for dx, dy in offsets:
        lat, lng = move_location(base_lat, base_lng, dx, dy)
        logging.info(f"[Block dx={dx}, dy={dy}]")
        places = fetch_places(lat, lng)
        all_places.extend(places)
        heatmap_points.append({"lat": lat, "lng": lng, "count": len(places)})

    unique = {p["place_id"]: p for p in all_places}.values()
    save_to_db(unique, heatmap_points)

    logging.info(f"総ユニーク件数: {len(unique)} 件を {DB_FILE} に保存しました。")

if __name__ == "__main__":
    main()
