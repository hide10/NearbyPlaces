# grab_nearby_restaurants

Google Maps API を利用して、指定エリアの飲食店情報を取得し、ヒートマップや一覧表示を可能にするツールセットです。

## 概要

このプロジェクトは以下の機能を提供します：

- Google Maps API から「restaurant」情報を取得し、SQLite データベースに保存
- 取得済みデータをもとにヒートマップを生成
- 自作ビュアーで駅前飲食店の一覧を閲覧可能

## 使用技術

- Python 3
- Google Maps Places API, Geocoding API, Distance Matrix API
- SQLite
- Folium（ヒートマップ生成用）
- Flask（任意でビュアーに拡張可）

## APIキーの取得手順

1. Google Cloud Console にアクセス  
   https://console.cloud.google.com/

2. プロジェクトを作成（または既存のプロジェクトを選択）

3. 左側メニューから「API とサービス」→「ライブラリ」を選択

4. 以下の API を有効化：
   - **Places API**
   - **Distance Matrix API**

5. 左メニューの「認証情報」→「APIキーを作成」をクリック

6. 発行されたキーを `.env` ファイルに記述：
   ```
   GMAPS_API_KEY=発行されたキーをここに貼り付け
   ```

7. 必要に応じて「制限」タブから使用APIの制限を設定（セキュリティ向上のため推奨）

## セットアップ

1. 必要ライブラリのインストール

```
pip install -r requirements.txt
```

2. `.env` ファイルをプロジェクトルートに作成し、以下のように記述：

```
GMAPS_API_KEY=your_api_key_here
LOCATION=35.681236,139.767125
RADIUS=500
TYPE=restaurant
LANG=ja
DB_FILE=restaurants.db
ITERATIONS=1
```

このキーは Places API と Distance Matrix API の両方に使用されます。

## スクリプト概要

### `grab_nearby_restaurants.py`

指定座標・範囲で「restaurant」カテゴリのプレイス情報を取得し、SQLite DB に格納します。各店舗への車での移動時間を Distance Matrix API から取得し、`drive_time` 列として保存します。

### Google Places APIの取得上限について

`grab_nearby_restaurants.py` を実行した際に  
**「この地点で60件以上取得されました。取得漏れの可能性があります。」**  
という警告が表示された場合は、Google Places APIの仕様により一度に取得できる件数が上限に達している可能性があります。

この場合は、`.env` ファイルの `RADIUS` の値を小さく設定し、検索範囲を狭めて再度実行してください。  
これにより、1地点あたりの取得件数が減り、漏れなくデータを取得しやすくなります。

例:

```plaintext
RADIUS=300
```

### `generate_heatmap.py`

DB に保存された店舗の位置情報を使って `heatmap.html` を生成します。

### `view_db.py`

DB 内の店舗情報を駅名などの条件でフィルタし、一覧として標準出力に表示します。

### `heatmap.html`

生成されたヒートマップ。ブラウザで開くと視覚的に店舗の密集度を確認できます。

## 注意事項

- Google Maps API の利用には料金が発生する場合があります（無料枠あり）
- APIキーの漏洩に注意してください（`.env` は `.gitignore` に含まれています）

