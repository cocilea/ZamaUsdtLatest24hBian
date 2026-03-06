"""
读取最近24小时币安ZAMA/USDT交易对价格变化情况，生成15分钟级别价格变化点阵图
Fetch Binance ZAMA/USDT price data for the last 24 hours and generate a
15-minute interval price change dot matrix chart.
"""

import argparse
import time
import requests
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
from datetime import datetime, timezone, timedelta

# UTC+8 (China Standard Time) used for all time display
UTC8 = timezone(timedelta(hours=8))


BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"
SYMBOL = "ZAMAUSDT"
INTERVAL = "15m"
# 24 hours / 15 minutes = 96 candles
LIMIT = 96
# Minimum absolute range for the colour axis to avoid division by zero
# when all candles have identical open/close prices.
MIN_VMAX = 0.01
# Baseline factor for the filled area in the price panel; pulling the fill
# slightly below the minimum close prevents the fill from appearing flat.
FILL_BASELINE_FACTOR = 0.999


def fetch_klines(symbol: str = SYMBOL, interval: str = INTERVAL, limit: int = LIMIT) -> list:
    """Fetch kline (candlestick) data from Binance REST API."""
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    response = requests.get(BINANCE_KLINE_URL, params=params, timeout=15)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise requests.exceptions.HTTPError(
            f"Binance API error for {symbol} {interval}: {exc}"
        ) from exc
    return response.json()


def parse_klines(raw: list) -> dict:
    """
    Parse raw kline data into structured arrays.

    Binance kline fields:
      [0]  open_time (ms)
      [1]  open
      [2]  high
      [3]  low
      [4]  close
      [5]  volume
      ...
    """
    times = []
    opens = []
    closes = []
    highs = []
    lows = []
    volumes = []

    for k in raw:
        open_time = datetime.fromtimestamp(k[0] / 1000, tz=UTC8)
        times.append(open_time)
        opens.append(float(k[1]))
        closes.append(float(k[4]))
        highs.append(float(k[2]))
        lows.append(float(k[3]))
        volumes.append(float(k[5]))

    return {
        "times": times,
        "opens": np.array(opens),
        "closes": np.array(closes),
        "highs": np.array(highs),
        "lows": np.array(lows),
        "volumes": np.array(volumes),
    }


def compute_price_changes(data: dict) -> np.ndarray:
    """Compute percentage price change for each 15-minute candle (close vs open)."""
    pct_changes = (data["closes"] - data["opens"]) / data["opens"] * 100
    return pct_changes


def build_dot_matrix(pct_changes: np.ndarray, n_rows: int = 20) -> tuple:
    """
    Build a 2-D dot matrix where:
      - X axis: time slots (one per 15-minute candle)
      - Y axis: price-change magnitude levels (from negative to positive)

    Each column has a single highlighted dot at the level corresponding to
    that candle's percentage price change.  The colour encodes the sign and
    magnitude of the change (red = down, green = up).

    Returns:
        matrix  – 2-D boolean array (n_rows × n_candles) marking lit dots
        y_ticks – centre value for each row
        vmax    – absolute maximum pct change (used for colour normalisation)
    """
    n_candles = len(pct_changes)
    vmax = max(abs(pct_changes).max(), MIN_VMAX)   # guard against all-zero data

    # Row 0 = most negative, row (n_rows-1) = most positive
    y_ticks = np.linspace(-vmax, vmax, n_rows)
    matrix = np.zeros((n_rows, n_candles), dtype=float)

    for col, pct in enumerate(pct_changes):
        # Find closest row
        row = int(np.argmin(np.abs(y_ticks - pct)))
        matrix[row, col] = pct   # store actual value so colour can reflect it

    return matrix, y_ticks, vmax


def plot_dot_matrix(data: dict, pct_changes: np.ndarray, output_path: str = "zama_dot_matrix.png"):
    """Render and save the dot-matrix chart."""
    matrix, y_ticks, vmax = build_dot_matrix(pct_changes)
    n_rows, n_candles = matrix.shape
    times = data["times"]

    fig, axes = plt.subplots(
        3, 1,
        figsize=(max(14, n_candles * 0.18), 13),
        gridspec_kw={"height_ratios": [3, 1, 1]},
    )
    fig.patch.set_facecolor("#0d1117")

    # ── Upper panel: dot matrix ──────────────────────────────────────────────
    ax = axes[0]
    ax.set_facecolor("#0d1117")

    # Draw background grid dots
    for row in range(n_rows):
        for col in range(n_candles):
            ax.scatter(col, row, s=18, color="#1e2a38", zorder=1, marker="o")

    # Draw highlighted (lit) dots
    cmap_pos = plt.cm.Greens
    cmap_neg = plt.cm.Reds

    for col in range(n_candles):
        for row in range(n_rows):
            val = matrix[row, col]
            if val != 0:
                norm_intensity = min(abs(val) / vmax, 1.0)
                if val > 0:
                    color = cmap_pos(0.4 + 0.6 * norm_intensity)
                else:
                    color = cmap_neg(0.4 + 0.6 * norm_intensity)
                ax.scatter(col, row, s=55, color=color, zorder=3, marker="o",
                           edgecolors="none")

    # Y-axis: price-change percentage labels
    step = max(1, n_rows // 10)
    ax.set_yticks(range(0, n_rows, step))
    ax.set_yticklabels(
        [f"{y_ticks[i]:+.2f}%" for i in range(0, n_rows, step)],
        color="#aab4c4", fontsize=8,
    )

    # X-axis: time labels (every 4 candles = 1 hour)
    tick_cols = list(range(0, n_candles, 4))
    ax.set_xticks(tick_cols)
    ax.set_xticklabels(
        [times[i].strftime("%H:%M") for i in tick_cols],
        rotation=45, ha="right", color="#aab4c4", fontsize=8,
    )

    ax.set_xlim(-0.5, n_candles - 0.5)
    ax.set_ylim(-0.5, n_rows - 0.5)
    ax.tick_params(colors="#aab4c4")
    for spine in ax.spines.values():
        spine.set_edgecolor("#2a3a4a")

    # Zero line
    zero_row = int(np.argmin(np.abs(y_ticks)))
    ax.axhline(zero_row, color="#4a5a6a", linewidth=0.8, linestyle="--", zorder=2)

    ax.set_title(
        f"ZAMA/USDT · 15-Minute Price Change Dot Matrix · Last 24 Hours\n"
        f"(CST/UTC+8  {times[0].strftime('%Y-%m-%d %H:%M')}  →  {times[-1].strftime('%Y-%m-%d %H:%M')})",
        color="#e6edf3", fontsize=11, pad=12,
    )
    ax.set_ylabel("Price Change (%)", color="#aab4c4", fontsize=9)

    # ── Lower panel: close-price line ────────────────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor("#0d1117")
    x = np.arange(n_candles)
    closes = data["closes"]

    # colour segments by direction
    for i in range(n_candles - 1):
        seg_color = "#3fb950" if closes[i + 1] >= closes[i] else "#f85149"
        ax2.plot([x[i], x[i + 1]], [closes[i], closes[i + 1]],
                 color=seg_color, linewidth=1.2)

    ax2.fill_between(x, closes, closes.min() * FILL_BASELINE_FACTOR,
                     color="#1f6feb", alpha=0.15)

    ax2.set_xlim(-0.5, n_candles - 0.5)
    ax2.set_xticks(tick_cols)
    ax2.set_xticklabels(
        [times[i].strftime("%H:%M") for i in tick_cols],
        rotation=45, ha="right", color="#aab4c4", fontsize=8,
    )
    ax2.tick_params(colors="#aab4c4")
    ax2.set_ylabel("Price (USDT)", color="#aab4c4", fontsize=9)
    for spine in ax2.spines.values():
        spine.set_edgecolor("#2a3a4a")

    # Colour bars as legend
    sm_pos = plt.cm.ScalarMappable(cmap=cmap_pos, norm=mcolors.Normalize(0, vmax))
    sm_neg = plt.cm.ScalarMappable(cmap=cmap_neg, norm=mcolors.Normalize(-vmax, 0))
    cb_pos = fig.colorbar(sm_pos, ax=axes[0], location="right", pad=0.01,
                          fraction=0.015, aspect=30)
    cb_pos.set_label("Rise (%)", color="#aab4c4", fontsize=8)
    cb_pos.ax.yaxis.set_tick_params(color="#aab4c4", labelcolor="#aab4c4")

    # ── Bottom panel: volume bars ─────────────────────────────────────────────
    ax3 = axes[2]
    ax3.set_facecolor("#0d1117")
    volumes = data["volumes"]

    # colour each bar by price direction (green = up, red = down)
    bar_colors = [
        "#3fb950" if closes[i] >= data["opens"][i] else "#f85149"
        for i in range(n_candles)
    ]
    ax3.bar(x, volumes, color=bar_colors, width=0.7, zorder=2)

    ax3.set_xlim(-0.5, n_candles - 0.5)
    ax3.set_xticks(tick_cols)
    ax3.set_xticklabels(
        [times[i].strftime("%H:%M") for i in tick_cols],
        rotation=45, ha="right", color="#aab4c4", fontsize=8,
    )
    ax3.tick_params(colors="#aab4c4")
    ax3.set_ylabel("成交量", color="#aab4c4", fontsize=9)
    for spine in ax3.spines.values():
        spine.set_edgecolor("#2a3a4a")

    # Format y-axis ticks with K/M suffix for readability
    def _vol_formatter(val, _pos):
        abs_val = abs(val)
        if abs_val >= 1_000_000:
            return f"{val/1_000_000:.1f}M"
        if abs_val >= 1_000:
            return f"{val/1_000:.0f}K"
        return f"{val:.0f}"

    ax3.yaxis.set_major_formatter(mticker.FuncFormatter(_vol_formatter))

    plt.tight_layout(pad=1.5)
    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Chart saved to: {output_path}")


def fetch_current_price(symbol: str = SYMBOL) -> float:
    """Fetch the latest trade price for *symbol* from the Binance ticker API."""
    response = requests.get(BINANCE_TICKER_URL, params={"symbol": symbol}, timeout=10)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise requests.exceptions.HTTPError(
            f"Binance ticker API error for {symbol}: {exc}"
        ) from exc
    return float(response.json()["price"])


def get_chart_json_data(data: dict, pct_changes: np.ndarray) -> dict:
    """Return chart data as a JSON-serialisable dict for the interactive frontend chart.

    Args:
        data: Parsed kline dict with keys 'times', 'opens', 'highs', 'lows',
              'closes', 'volumes' as returned by :func:`parse_klines`.
        pct_changes: 1-D array of per-candle percentage changes (close vs open)
                     as returned by :func:`compute_price_changes`.

    Returns:
        Dict with keys:
          - ``times``:      list of CST/UTC+8 time strings (``YYYY-MM-DD HH:MM``)
          - ``ohlcv``:      list of ``[open, high, low, close, volume]`` floats
          - ``pct_changes``: list of float pct change values
          - ``dot_matrix``: dict with 'matrix', 'y_ticks', 'n_rows', 'vmax'
    """
    matrix, y_ticks, vmax = build_dot_matrix(pct_changes)
    n_rows, n_candles = matrix.shape
    times = data["times"]

    return {
        "times": [t.strftime("%Y-%m-%d %H:%M") for t in times],
        "ohlcv": [
            [
                float(data["opens"][i]),
                float(data["highs"][i]),
                float(data["lows"][i]),
                float(data["closes"][i]),
                float(data["volumes"][i]),
            ]
            for i in range(n_candles)
        ],
        "pct_changes": [float(v) for v in pct_changes],
        "dot_matrix": {
            "matrix": matrix.tolist(),
            "y_ticks": [float(v) for v in y_ticks],
            "n_rows": n_rows,
            "vmax": float(vmax),
        },
    }


def print_summary(data: dict, pct_changes: np.ndarray):
    """Print a brief text summary to stdout."""
    times = data["times"]
    closes = data["closes"]
    total_change = (closes[-1] - closes[0]) / closes[0] * 100
    max_idx = int(np.argmax(pct_changes))
    min_idx = int(np.argmin(pct_changes))

    print("=" * 60)
    print(f"  Symbol  : ZAMA/USDT")
    print(f"  Period  : {times[0].strftime('%Y-%m-%d %H:%M')} CST"
          f"  →  {times[-1].strftime('%Y-%m-%d %H:%M')} CST")
    print(f"  Candles : {len(times)} × 15 min")
    print(f"  Open    : {data['opens'][0]:.6f} USDT")
    print(f"  Close   : {closes[-1]:.6f} USDT")
    print(f"  24h Chg : {total_change:+.2f}%")
    print(f"  Max rise: {pct_changes[max_idx]:+.2f}%  @ {times[max_idx].strftime('%H:%M')} CST")
    print(f"  Max drop: {pct_changes[min_idx]:+.2f}%  @ {times[min_idx].strftime('%H:%M')} CST")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Binance ZAMA/USDT 15-min klines and generate a price-change dot-matrix chart."
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="zama_dot_matrix.png",
        help="Output PNG file path (default: zama_dot_matrix.png)",
    )
    args = parser.parse_args()

    print(f"Fetching {SYMBOL} {INTERVAL} klines from Binance …")
    raw = fetch_klines()
    print(f"  Received {len(raw)} candles.")

    data = parse_klines(raw)
    pct_changes = compute_price_changes(data)

    print_summary(data, pct_changes)
    plot_dot_matrix(data, pct_changes, output_path=args.output)


if __name__ == "__main__":
    main()
