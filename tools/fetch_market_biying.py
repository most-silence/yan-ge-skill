"""fetch_market_biying.py — 必盈API 拉沪深指数日线（含成交额）。

免费版配额 100 次/天，本脚本仅需 4 次（每个指数 1 次，一次返回 1990 年至今全量）。
返回字段：t 日期 / o 开 / c 收 / h 高 / l 低 / v 成交量 / a 成交额(元) / pc 前收

用法：python fetch_market_biying.py
输出：research/大盘数据.json（覆盖旧版，新增 amount 与 pct/vol_chg_pct 派生字段）
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

LICENCE = "570F2E84-C47B-4CE0-B1D7-5E06634B5E9A"
OUT = Path(r"E:\AIProjetct\Nothing\眼哥\research\大盘数据.json")

INDICES = [
    ("上证", "000001.SH"),
    ("深证", "399001.SZ"),
    ("创业板", "399006.SZ"),
    ("科创50", "000688.SH"),
]

# 保留区间：2025-01-01 起（覆盖播客全量期），更早的丢弃以免文件臃肿
KEEP_FROM = "2025-01-01"


def fetch(code):
    url = f"http://api.biyingapi.com/hsindex/history/{code}/d/{LICENCE}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(req, timeout=40).read().decode("utf-8")
            return json.loads(raw)
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  {code} 重试 {attempt + 1}: {type(e).__name__}", flush=True)
            time.sleep(3)


def main():
    out = {"source": "必盈API hsindex/history（含成交额 a）",
           "licence_used": LICENCE[:8] + "…",
           "keep_from": KEEP_FROM, "indices": {}}

    for name, code in INDICES:
        print(f"拉取 {name} ({code}) …", flush=True)
        bars = fetch(code)
        rows = []
        for b in bars:
            if b["t"] < KEEP_FROM:
                continue
            rows.append({
                "date": b["t"], "open": b["o"], "close": b["c"],
                "high": b["h"], "low": b["l"],
                "volume": b["v"], "amount": b["a"],
                "prev_close": b["pc"],
            })
        # 派生：涨跌幅、成交额环比、量环比
        for i, r in enumerate(rows):
            if r["prev_close"]:
                r["pct"] = round((r["close"] - r["prev_close"]) / r["prev_close"] * 100, 2)
            if i:
                p = rows[i - 1]
                if p["amount"]:
                    r["amt_chg_pct"] = round((r["amount"] - p["amount"]) / p["amount"] * 100, 2)
                if p["volume"]:
                    r["vol_chg_pct"] = round((r["volume"] - p["volume"]) / p["volume"] * 100, 2)
        out["indices"][name] = rows
        print(f"  {len(rows)} 条，{rows[0]['date']} → {rows[-1]['date']}，"
              f"最新成交额 {rows[-1]['amount'] / 1e8:,.0f} 亿", flush=True)
        time.sleep(2)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写入 {OUT}（{OUT.stat().st_size / 1024:.0f} KB，消耗 4 次配额）")


if __name__ == "__main__":
    main()
