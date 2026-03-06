"""
Flask web application to display the ZAMA/USDT 15-minute price change
dot-matrix chart in a browser.

Routes:
  GET /            – HTML page with the interactive ECharts chart
  GET /chart.png   – Dynamically generated static chart image (PNG)
  GET /chart-data  – JSON payload for the interactive frontend chart
  GET /price       – JSON with the latest ZAMA/USDT spot price

Environment variables:
  FLASK_DEBUG   – Set to "1" to enable Flask debug mode (default: off).
  CHART_TTL     – Seconds to cache the generated chart/data (default: 60).
  PRICE_TTL     – Seconds to cache the spot price (default: 15).
"""

import io
import os
import time
import threading

from flask import Flask, Response, render_template, jsonify

from zama_price_chart import (
    fetch_klines,
    fetch_current_price,
    parse_klines,
    compute_price_changes,
    plot_dot_matrix,
    get_chart_json_data,
)

app = Flask(__name__)

# Cache settings
_CHART_TTL = int(os.environ.get("CHART_TTL", "60"))   # seconds
_PRICE_TTL = int(os.environ.get("PRICE_TTL", "15"))   # seconds

# ── Shared parsed-data cache (avoids hitting Binance twice for PNG + JSON) ──
_data_lock = threading.Lock()
_data_cache: tuple = ()          # (data_dict, pct_changes_array)
_data_cache_time: float = 0.0

# ── Rendered PNG cache ───────────────────────────────────────────────────────
_chart_lock = threading.Lock()
_chart_cache: bytes = b""
_chart_cache_time: float = 0.0

# ── Spot-price cache ─────────────────────────────────────────────────────────
_price_lock = threading.Lock()
_price_cache: float = 0.0
_price_cache_time: float = 0.0


def _get_cached_data() -> tuple:
    """Return (data, pct_changes), re-fetching from Binance when TTL expires."""
    global _data_cache, _data_cache_time  # noqa: PLW0603
    with _data_lock:
        if not _data_cache or (time.monotonic() - _data_cache_time) > _CHART_TTL:
            raw = fetch_klines()
            data = parse_klines(raw)
            pct_changes = compute_price_changes(data)
            _data_cache = (data, pct_changes)
            _data_cache_time = time.monotonic()
        return _data_cache


def _get_cached_chart() -> bytes:
    """Return a cached PNG, regenerating it when the cache has expired."""
    global _chart_cache, _chart_cache_time  # noqa: PLW0603
    with _chart_lock:
        if not _chart_cache or (time.monotonic() - _chart_cache_time) > _CHART_TTL:
            data, pct_changes = _get_cached_data()
            buf = io.BytesIO()
            plot_dot_matrix(data, pct_changes, output_path=buf)
            buf.seek(0)
            _chart_cache = buf.read()
            _chart_cache_time = time.monotonic()
        return _chart_cache


def _get_cached_price() -> float:
    """Return the latest spot price, re-fetching when PRICE_TTL expires."""
    global _price_cache, _price_cache_time  # noqa: PLW0603
    with _price_lock:
        if not _price_cache or (time.monotonic() - _price_cache_time) > _PRICE_TTL:
            _price_cache = fetch_current_price()
            _price_cache_time = time.monotonic()
        return _price_cache


@app.route("/chart.png")
def chart_png():
    """Return the dot-matrix chart as a PNG image."""
    image_data = _get_cached_chart()
    return Response(image_data, mimetype="image/png")


@app.route("/chart-data")
def chart_data_endpoint():
    """Return all chart series data as JSON for the interactive ECharts frontend."""
    data, pct_changes = _get_cached_data()
    return jsonify(get_chart_json_data(data, pct_changes))


@app.route("/price")
def price_endpoint():
    """Return the latest ZAMA/USDT spot price as JSON."""
    price = _get_cached_price()
    return jsonify({"symbol": "ZAMAUSDT", "price": price})


@app.route("/")
def index():
    """Render the main HTML page."""
    return render_template("index.html")


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
