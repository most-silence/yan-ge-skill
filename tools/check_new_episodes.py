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


def fetch_latest_page(retries=4):
    """抓播客列表首页（Livewire 首页 SSR 含最新 12 期）。

    ⚠️ 教训：earsonme 的分页走 Livewire XHR，`?page=N` 参数无效——
    翻多页只会反复拿到同一批最新 12 期。所以这里只取首页，但
    新发布的期次一定排在首页里，「有没有新期」的判断不受影响。
    首页偶发超时，必须重试；首页拿不到就返回 None（绝不静默当无新期）。
    """
    import time
    import urllib.request
    url = "https://earsonme.com" + PODCAST_PATH
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", "ignore")
            ids = set(EP_RE.findall(html))
            if len(ids) >= 5:           # 首页应有 12 期，太少视为残缺页
                return ids
            last_err = f"首页 eid 过少（{len(ids)}），疑似残缺/拦截"
        except Exception as e:
            last_err = str(e)
        time.sleep(3 * (attempt + 1))    # 退避重试
    print(f"  首页抓取失败：{last_err}")
    return None


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

    remote = fetch_latest_page()
    via = "http"
    if remote is None:
        print("HTTP 首页拿不到，尝试 CDP …")
        remote = fetch_via_cdp()
        via = "cdp"
        if remote is None:
            print("远端不可达（HTTP 与 CDP 都失败）。下次再查。")
            STATE.write_text(json.dumps(
                {"last": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                 "status": "unreachable", "known": len(known)},
                ensure_ascii=False), encoding="utf-8")
            return 2

    # 防漏检校验：首页应与本地基准大量重叠（我们刚处理过最新期）。
    # 若首页 eid 与本地完全不相交，多半是解析/站点结构变了，不能谎报「无新期」。
    overlap = remote & known
    if remote and not overlap:
        print(f"⚠️ 首页 {len(remote)} 个 eid 与本地基准零重叠——疑似解析失效或站点改版，"
              f"本次不下「无新期」结论，请人工核查。")
        STATE.write_text(json.dumps(
            {"last": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
             "status": "suspicious", "via": via, "known": len(known),
             "remote_seen": len(remote), "overlap": 0},
            ensure_ascii=False, indent=1), encoding="utf-8")
        return 2

    new = remote - known
    now = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    STATE.write_text(json.dumps(
        {"last": now, "status": "ok", "via": via,
         "known": len(known), "remote_seen": len(remote),
         "overlap": len(overlap), "new": sorted(new)}, ensure_ascii=False, indent=1), encoding="utf-8")

    if not new:
        print(f"远端未见新期（首页 {len(remote)} 个 eid，其中 {len(overlap)} 个已知）。")
        return 0
    print(f"\n发现 {len(new)} 个新期：")
    for e in sorted(new):
        print(f"  {e}")
    print("\n→ 按 蒸馏执行手册.md 增量协议走完整管线（下载→转写→批读→归并→SKILL 升版）")
    return 1


if __name__ == "__main__":
    sys.exit(main())