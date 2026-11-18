#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""download_new_audio.py — 下载 _新期manifest.json 里的音频（官方直链，匿名可取）

命名规范与全量一致：audio/{oid24}_{title}.m4a（标题清洗文件名非法字符）。
oid24 是官方 24 位 id；批读输入用 oid 前 12 位作期次 ID 时需注意——
本项目历史 eid 是 12 位小宇宙短 id，与 24 位 oid **不是截断关系**，
所以下载后要把 oid→title→真实 12 位 eid 的映射建好（从单集页 SSR 取）。
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

MANIFEST = ROOT / "research" / "_新期manifest.json"
OUT_DIR = ROOT / "sources" / "00-原始素材" / "earsonme" / "audio"
EID_MAP = ROOT / "research" / "_新期eid映射.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"}


def safe_name(t):
    return re.sub(r'[\\/:*?"<>|]', "_", t).strip()[:60]


def main():
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    print(f"下载 {len(items)} 期")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 单集页取真实 12 位短 eid（页面里 episode 数据有 "eid" 字段——24位；
    # 但小宇宙内部短 id 在 shareUrl / 播放器配置里。先探一次结构）
    total = 0
    for it in items:
        oid, title, url = it["oid"], it["title"], it["media_url"]
        dest = OUT_DIR / f"{oid}_{safe_name(title)}.m4a"
        if dest.exists() and dest.stat().st_size > 100_000:
            print(f"  {title[:28]} 已有，跳过")
            continue
        try:
            req = urllib.request.Request(url, headers={**UA, "Referer": "https://www.xiaoyuzhoufm.com/"})
            with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            mb = dest.stat().st_size / 1e6
            total += mb
            print(f"  {title[:28]:<30} {mb:5.1f} MB")
        except Exception as e:
            print(f"  {title[:28]} 下载失败: {e}")
        time.sleep(1)

    print(f"\n本轮流量 {total:.1f} MB")

    # 新批次直接用官方 24 位 oid 作期次 ID（唯一稳定，全链路自洽；
    # 不再强求映射历史 12 位短 eid——两套编码本无截断关系，混用反而易错）
    EID_MAP.write_text(json.dumps(
        [{"oid": it["oid"], "title": it["title"], "duration_sec": it["duration_sec"]}
         for it in items], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ research/_新期eid映射.json（{len(items)} 条，oid 作 ID）")


if __name__ == "__main__":
    main()
