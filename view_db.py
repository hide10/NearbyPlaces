from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
from math import radians, cos, sin, asin, sqrt
import os
import random
from dotenv import load_dotenv

# .env読込み
load_dotenv()

app = Flask(__name__)

# 環境変数
location_str = os.getenv("LOCATION", "0,0")
DB_FILE = os.getenv("DB_FILE", "restaurants.db")
base_lat, base_lng = map(float, location_str.split(","))

def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * asin(sqrt(a))
    return R * c * 1000

def get_restaurants(hidden=0):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM restaurants WHERE hidden=?", (hidden,))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "place_id": row["place_id"],
            "name": row["name"],
            "address": row["address"],
            "rating": row["rating"],
            "distance": haversine(base_lat, base_lng, row["lat"], row["lng"]),
            "drive_time": row["drive_time"],
            "maps_url": row["maps_url"],
            "last_visited": row["last_visited"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

@app.route("/")
def index():
    restaurants = get_restaurants(hidden=0)
    return render_template_string(INDEX_HTML, restaurants=restaurants)

@app.route("/random")
def random_pick():
    restaurants = get_restaurants(hidden=0)
    pick = random.sample(restaurants, min(3, len(restaurants)))
    return render_template_string(RANDOM_HTML, restaurants=pick)

@app.route("/hidden")
def show_hidden():
    restaurants = get_restaurants(hidden=1)
    return render_template_string(HIDDEN_HTML, restaurants=restaurants)

@app.route("/hide/<place_id>", methods=["POST"])
def hide(place_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE restaurants SET hidden=1 WHERE place_id=?", (place_id,))
    conn.commit(); conn.close()
    return redirect(url_for('index'))

@app.route("/unhide/<place_id>", methods=["POST"])
def unhide(place_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE restaurants SET hidden=0 WHERE place_id=?", (place_id,))
    conn.commit(); conn.close()
    return redirect(url_for('show_hidden'))

@app.route("/update_last_visited/<place_id>", methods=["POST"])
def update_last_visited(place_id):
    last_visited = request.form.get("last_visited")
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "UPDATE restaurants SET last_visited=?, updated_at=datetime('now', 'localtime') WHERE place_id=?",
        (last_visited, place_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# 一覧表示用
INDEX_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>レストラン一覧</title>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
<style>
.last-visited-text {
  display: inline-block;
  min-width: 60px;
  min-height: 1.5em;
  cursor: pointer;
  background: #f0f0f0;
  border-radius: 3px;
  padding: 2px 4px;
}
</style>
</head>
<body>
<h2>レストラン一覧</h2>
<a href="{{ url_for('show_hidden') }}">非表示リストを見る</a>
<form method="get" action="{{ url_for('random_pick') }}">
    <button type="submit">ランダムに3件表示</button>
</form>
<table id="mytable" class="display">
<thead>
<tr>
<th>名前</th><th>住所</th><th>評価</th><th>距離(m)</th><th>移動時間(分)</th><th>最終訪店日</th><th>更新日</th><th>Google Maps</th><th>操作</th>
</tr>
</thead>
<tbody>
{% for r in restaurants %}
<tr>
<td>{{ r['name'] }}</td>
<td>{{ r['address'] }}</td>
<td>{{ r['rating'] or '' }}</td>
<td>{{ "%.0f"|format(r['distance']) }}</td>
<td>{{ "%.0f"|format((r['drive_time'] or 0)/60) if r['drive_time'] else '' }}</td>
<td>
  <span class="last-visited-text" data-place-id="{{ r['place_id'] }}">
  {{ r['last_visited'] or '未入力' }}
</span>
  <form class="last-visited-form" method="post" action="{{ url_for('update_last_visited', place_id=r['place_id']) }}" style="display:none;">
    <input type="date" name="last_visited" value="{{ r['last_visited'] or '' }}">
    <button type="submit">保存</button>
    <button type="button" class="cancel-btn">キャンセル</button>
  </form>
</td>
<td>{{ r['updated_at'] or '' }}</td>
<td><a href="{{ r['maps_url'] }}" target="_blank">地図で見る</a></td>
<td>
  <form class="hide-form" method="post" action="{{ url_for('hide', place_id=r['place_id']) }}">
    <button type="submit">非表示</button>
  </form>
</td>
</tr>
{% endfor %}
</tbody>
</table>
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script>
$(document).ready(function() {
    $('#mytable').DataTable({ "pageLength": -1 });

    // 非表示ボタンのAjax化
    $('.hide-form').on('submit', function(e){
        e.preventDefault();
        var $row = $(this).closest('tr');
        var actionUrl = $(this).attr('action');
        $.post(actionUrl, function(){
            // 行を非表示にする
            $row.fadeOut(300, function(){ $(this).remove(); });
        });
    });
});
$(function(){
  $('.last-visited-text').on('click', function(){
    $(this).hide().next('.last-visited-form').show();
  });
  $('.cancel-btn').on('click', function(){
    $(this).closest('.last-visited-form').hide().prev('.last-visited-text').show();
  });
});
</script>
</body>
</html>
"""

# ランダム表示用
RANDOM_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"><title>ランダム3件</title></head>
<body>
<h2>ランダムに選ばれた3件</h2>
<a href="{{ url_for('index') }}">一覧に戻る</a>
<form method="get" action="{{ url_for('random_pick') }}">
    <button type="submit">もう一度ランダム3件を選ぶ</button>
</form>
<table border="1">
<thead>
<tr>
<th>名前</th><th>住所</th><th>評価</th><th>距離(m)</th><th>移動時間(分)</th><th>最終訪店日</th><th>更新日</th><th>Google Maps</th><th>操作</th>
</tr>
</thead>
<tbody>
{% for r in restaurants %}
<tr>
<td>{{ r['name'] }}</td>
<td>{{ r['address'] }}</td>
<td>{{ r['rating'] or '' }}</td>
<td>{{ "%.0f"|format(r['distance']) }}</td>
<td>{{ "%.0f"|format((r['drive_time'] or 0)/60) if r['drive_time'] else '' }}</td>
<td>{{ r['last_visited'] or '' }}</td>
<td>{{ r['updated_at'] or '' }}</td>
<td><a href="{{ r['maps_url'] }}" target="_blank">地図で見る</a></td>
<td>
  <form class="hide-form" method="post" action="{{ url_for('hide', place_id=r['place_id']) }}">
    <button type="submit">非表示</button>
  </form>
</td>
</tr>
{% endfor %}
</tbody>
</table>
</body>
</html>
"""

# 非表示リスト用
HIDDEN_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>非表示レストラン</title>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
</head>
<body>
<h2>非表示レストラン</h2>
<a href="{{ url_for('index') }}">表示リストに戻る</a>
<table id="hidden_table" class="display">
<thead>
<tr>
<th>名前</th><th>住所</th><th>移動時間(分)</th><th>最終訪店日</th><th>更新日</th><th>Google Maps</th><th>操作</th>
</tr>
</thead>
<tbody>
{% for r in restaurants %}
<tr>
<td>{{ r['name'] }}</td>
<td>{{ r['address'] }}</td>
<td>{{ "%.0f"|format((r['drive_time'] or 0)/60) if r['drive_time'] else '' }}</td>
<td>{{ r['last_visited'] or '' }}</td>
<td>{{ r['updated_at'] or '' }}</td>
<td><a href="{{ r['maps_url'] }}" target="_blank">地図で見る</a></td>
<td>
  <form method="post" action="{{ url_for('unhide', place_id=r['place_id']) }}">
    <button type="submit">再表示</button>
  </form>
</td>
</tr>
{% endfor %}
</tbody>
</table>
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script>
$(document).ready(function() {
    $('#hidden_table').DataTable();
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run()
