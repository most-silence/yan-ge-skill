#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_new_episodes.py — 眼哥播客增量体检（官方小宇宙源，v2）

v1 的致命错误：拿第三方镜像站 earsonme 当权威源。镜像同步滞后
（官方已到 11-17，镜像还停在 11-04），导致「无新期」误报，
差点漏掉一整周的新节目。

v2 改用**官方小宇宙**为源：
  - 列表页 SSR 的 __NEXT_DATA__ 直接给最新 15 期（oid + 标题）
  - 单集页 SSR 直接内嵌 media.xyzcdn.net 音频直链——镜像根本不需要
  - 与本地按**标题**比对（标题是人读稳定键；官方 oid 24 位与本地
    12 位 eid 是两套编码，不能直接比 id）

退出码：0=无新期  1=有新期（打印 manifest）  2=不可达/可疑
"""

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "research" / "_增量体检.json"
MANIFEST = ROOT / "research" / "_新期manifest.json"
PODCAST_ID = "6860f13d09b4c8a7b539a3f8"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}

# 本地已收录标题索引（含无标题的纯 eid 期次，从元数据补）
AUDIO_TXT = ROOT / "sources" / "05-播客转写" / "audio_txt"
META = ROOT / "research" / "_新期元数据.json"
TRACKED = ROOT / "research" / "_已收录标题.json"


def norm_title(t):
    """标题归一：去空格、全角转半角近似、小写"""
    t = re.sub(r"\s+", "", t or "")
    return t.lower()


def local_titles():
    """本地已收录的标题集合。"""
    out = set()
    if AUDIO_TXT.exists():
        for f in AUDIO_TXT.glob("*._clean.txt"):
            # {eid}_{title}._clean.txt 或 {eid}._clean.txt
            stem = f.name[:-len("._clean.txt")]
            parts = stem.split("_", 1)
            title = parts[1] if len(parts) > 1 else ""
            if title:
                out.add(norm_title(title))
    # 纯 eid 期次的标题在元数据/已收录清单里
    for p in (META, TRACKED):
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                items = d if isinstance(d, list) else list(d.values()) if isinstance(d, dict) else []
                for it in items:
                    if isinstance(it, dict) and it.get("title"):
                        out.add(norm_title(it["title"]))
                    elif isinstance(it, str):
                        out.add(norm_title(it))
            except Exception:
                pass
    return out


def fetch_json(url, retries=4):
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(3 * (a + 1))
    raise RuntimeError(f"抓取失败 {url}: {last}")


def next_data(body):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
    return json.loads(m.group(1)) if m else None


def list_episodes():
    """官方列表页 → 最新 15 期 [{oid, title}]"""
    body = fetch_json(f"https://www.xiaoyuzhoufm.com/podcast/{PODCAST_ID}")
    data = next_data(body)
    eps = data["props"]["pageProps"]["podcast"]["episodes"]
    return [{"oid": e.get("eid", ""), "title": e.get("title", "").strip()}
            for e in eps if e.get("eid")]


def episode_media(oid):
    """官方单集页 → media 直链 + 时长"""
    body = fetch_json(f"https://www.xiaoyuzhoufm.com/episode/{oid}")
    m = re.search(r"https://media\.xyzcdn\.net/[^\"\\ ]+\.m4a", body)
    url = m.group(0) if m else ""
    # 时长（秒）
    d = re.search(r'"duration":(\d+)', body)
    dur = int(d.group(1)) if d else 0
    return url, dur


def main():
    known = local_titles()
    print(f"本地已收录标题：{len(known)} 个")

    try:
        eps = list_episodes()
    except Exception as e:
        print(f"列表页抓取失败：{e}")
        STATE.write_text(json.dumps({"status": "unreachable", "error": str(e)},
                                    ensure_ascii=False), encoding="utf-8")
        return 2

    if len(eps) < 5:
        print(f"⚠️ 列表页仅 {len(eps)} 期，疑似解析失效，不下结论")
        return 2

    new = [e for e in eps if norm_title(e["title"]) not in known]
    print(f"官方最新 {len(eps)} 期，其中未收录 {len(new)} 期")

    if not new:
        STATE.write_text(json.dumps(
            {"status": "ok", "known_titles": len(known),
             "remote_latest": len(eps), "new": []}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print("无新期。")
        return 0

    manifest = []
    for e in new:
        try:
            url, dur = episode_media(e["oid"])
        except Exception as ex:
            print(f"  {e['title'][:24]} 单集页失败：{ex}")
            url, dur = "", 0
        manifest.append({"oid": e["oid"], "title": e["title"],
                         "media_url": url, "duration_sec": dur})
        print(f"  {e['title'][:28]:<30} {dur//60}分 {'✓直链' if url else '✗无直链'}")
        time.sleep(1.5)

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    STATE.write_text(json.dumps(
        {"status": "new", "known_titles": len(known),
         "remote_latest": len(eps), "new": [m["title"] for m in manifest]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    got = sum(1 for m in manifest if m["media_url"])
    print(f"\n新期 {len(manifest)} 个，拿到直链 {got} 个 → research/_新期manifest.json")
    print("→ 走增量管线：下载→转写→批读→归并→SKILL 评估")
    return 1


if __name__ == "__main__":
    sys.exit(main())
