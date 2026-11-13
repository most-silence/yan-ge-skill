#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_new_episodes.py — 眼哥播客增量体检（轻量，普通 HTTP）

定时任务入口：每 3 天跑一次，只做「有没有新一期」的判断（流量 < 1 MB）。
发现新期后，完整增量管线按 蒸馏执行手册.md 增量协议走（本脚本不管）。

本地基准：sources/05-播客转写/audio_txt/*._clean.txt 的文件名前 12 位 eid
（379 期全量转写的权威清单，不依赖任何中间 json）。

远端：earsonme 镜像站的播客列表页（SSR，前几页就是最新一期）。
普通 GET 若被 Cloudflare 拦，退回提示用 CDP（tools/earsonme_cdp_harvest.py --ids）。

退出码：0=无新期  1=有新期（打印新 eid 清单）  2=远端不可达
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO_TXT = ROOT / "sources" / "05-播客转写" / "audio_txt"
STATE = ROOT / "research" / "_增量体检.json"
# 镜像站真实路径（xiaoyuzhoufm 的 pid ≠ 镜像站的 podcast id，别混用）
PODCAST_PATH = "/podcasts/IQpid2Xv/episodes"
PAGES = 3          # 列表页每页 20+ 期，前 3 页覆盖最新 60+ 期，足够发现 3 天内的更新
EP_RE = re.compile(r"/episodes/([A-Za-z0-9]{12})")


def local_eids():
    out = set()
    if AUDIO_TXT.exists():
        for f in AUDIO_TXT.glob("*._clean.txt"):
            eid = f.name[:12]
            if re.fullmatch(r"[A-Za-z0-9]{12}", eid):
                out.add(eid)
    return out


def fetch_remote_pages():
    """普通 HTTP 抓列表页；被拦返回 None"""
    import urllib.request
    out = []
    for page in range(1, PAGES + 1):
        url = (f"https://earsonme.com{PODCAST_PATH}" if page == 1
               else f"https://earsonme.com{PODCAST_PATH}?page={page}")
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", "ignore")
        except Exception as e:
            print(f"  page {page} 失败: {e}")
            return None
        ids = set(EP_RE.findall(html))
        if not ids:
            return None
        out.append(ids)
    return out


def fetch_via_cdp():
    """HTTP 被拦时走 CDP（需要已开的调试浏览器）"""
    script = ROOT / "tools" / "earsonme_cdp_harvest.py"
    try:
        r = subprocess.run(
            [sys.executable, "-X", "utf8", str(script), "--ids"],
            capture_output=True, text=True, timeout=300, cwd=ROOT)
        ids_file = ROOT / "sources" / "00-原始素材" / "earsonme" / "_earsonme_ids.json"
        if ids_file.exists():
            return set(json.loads(ids_file.read_text(encoding="utf-8")))
    except Exception as e:
        print(f"  CDP 备选也失败: {e}")
    return None


def main():
    known = local_eids()
    print(f"本地基准：{len(known)} 期（audio_txt clean 稿）")

    pages = fetch_remote_pages()
    via = "http"
    if pages is None:
        print("普通 HTTP 被拦，尝试 CDP …")
        remote = fetch_via_cdp()
        via = "cdp"
        if remote is None:
            print("远端不可达（HTTP 与 CDP 都失败）。下次再查。")
            STATE.write_text(json.dumps(
                {"last": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                 "status": "unreachable", "known": len(known)},
                ensure_ascii=False), encoding="utf-8")
            return 2
    else:
        remote = set().union(*pages)

    new = remote - known
    now = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    STATE.write_text(json.dumps(
        {"last": now, "status": "ok", "via": via,
         "known": len(known), "remote_seen": len(remote),
         "new": sorted(new)}, ensure_ascii=False, indent=1), encoding="utf-8")

    if not new:
        print(f"远端未见新期（扫到 {len(remote)} 个 eid，全部已知）。")
        return 0
    print(f"\n发现 {len(new)} 个新期：")
    for e in sorted(new):
        print(f"  {e}")
    print("\n→ 按 蒸馏执行手册.md 增量协议走完整管线（下载→转写→批读→归并→SKILL 升版）")
    return 1


if __name__ == "__main__":
    sys.exit(main())