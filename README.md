# Nearby Restaurant Viewer 🍽

Google Maps API を使って自宅周辺の飲食店情報を取得し、SQLite に保存。  
Flask ビューアで一覧・編集・ランダム表示・非表示切替ができるローカルアプリです。

---

## 📦 構成ファイル

| ファイル名 | 内容 |
|------------|------|
| `grab_nearby_restaurants.py` | Google Places API を使って飲食店情報を取得し、SQLite に保存 |
| `view_db.py` | Flask ビューア本体（表示・編集・非表示処理） |
| `.env` | 各種設定（APIキー、座標、DBファイル名など） |

---

## 🛠 必要な環境

- Python 3.7 以上
- Google Cloud Platform アカウント
- `pip install -r requirements.txt`

```text
requests
python-dotenv
flask
```

---

## 🔐 `.env` 設定例

プロジェクトフォルダに `.env` ファイルを作成し、以下のように記述：

```env
GMAPS_API_KEY=あなたのAPIキー
LOCATION==35.6895,139.6917
RADIUS=500
TYPE=restaurant
LANG=ja
DB_FILE=restaurants.db
```

---

## 🔑 APIキーの取得手順（Places API）

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを作成（例：NearbyPlaces）
3. 「APIとサービス」→「ライブラリ」→「Places API」を検索＆有効化
4. 「認証情報」→「APIキーを作成」
5. `.env` の `GMAPS_API_KEY` に貼り付け

> ※課金アカウントの設定が必要です。無料枠あり。

---

## 🚀 データ取得方法（近所の飲食店を保存）

```bash
python grab_nearby_restaurants.py
```

実行すると `.env` で指定した半径内の飲食店が取得され、SQLite DB（例：`restaurants.db`）に保存されます。  
既存レコードは `place_id` をもとに重複を避け、`rating` 更新時は `updated_at` も更新されます。

---

## 👀 ビューア起動方法（Flask）

```bash
python view_db.py
```

起動後、`http://localhost:5000` にアクセスすると一覧画面が表示されます。

---

## 📋 ビューア機能

- ✅ 一覧表示（評価、距離、訪問日、更新日など）
- 🖋 最終訪店日の直接編集
- 🎲 ランダム3件の抽出表示
- 🚫 一時非表示 → ✅ 再表示切替
- 📏 距離計算は `.env` の `LOCATION` を基準に Haversine で算出

---

## 📁 DBスキーマ概要（SQLite）

| カラム名 | 説明 |
|----------|------|
| `place_id` | Googleの店舗ID（主キー） |
| `name` | 店名 |
| `address` | 住所 |
| `lat`, `lng` | 緯度経度 |
| `rating` | 評価（最大5.0） |
| `maps_url` | Googleマップリンク |
| `last_visited` | 手動で入力可能な訪問日（`YYYY-MM-DD`） |
| `hidden` | 非表示フラグ（0:表示中、1:非表示） |
| `updated_at` | Google情報の最終取得・更新時刻（自動更新） |

---

## 🧠 拡張案（必要に応じて）

- `genre` 列追加（店名キーワードから居酒屋・中華などを推定）
- `price_level`, `opening_hours` の取得と保存
- Map表示（folium / leaflet.js）との連携
- Web UIの分離（Jinjaテンプレート化、JSモジュール分離）

---

## 🐾 作者

hide10
> Embedded Software Developer｜Pythonでおいしい街を探索中  
> Blog: [https://www.hide10.com](https://www.hide10.com)

---

## 🧯 注意点

- Google APIには無料枠・課金枠の制限があります。**使いすぎ注意！**
- `.env` ファイルは `.gitignore` に追加して **絶対に公開しない**ようにしてください
