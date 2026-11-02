#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_more_episodes.py — 想办法拿到全部 378 集，而不只是首页 15 集

已知死路
--------
· `?page=N` 被忽略，永远返回同样 15 集（已实测 page=1/2/3/5 完全重合）
· `api.xiaoyuzhoufm.com/v1/episode/list-by-podcast/...` → 401
· `www.xiaoyuzhoufm.com/feed/{pid}` → 404
· `rss.xiaoyuzhoufm.com/{pid}` → 404
· 主页 HTML 里 `episodeCount: 378`，但只嵌了 15 集

待试
----
1. sitemap.xml / robots.txt 里有没有 episode 列表
2. 前端 JS bundle 里的真实接口名（可能带签名参数）
3. 单集页 URL 规律（若 eid 可枚举或可从搜索拿）
4. 移动端页面 / 分享页
5. 第三方镜像（Apple Podcasts 有这档节目会有 RSS 镜像！）
"""

import re
import sys
import urllib.request

PID = "6860f13d09b4c8a7b539a3f8"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def try_url(label, url, check=None):
    try:
        raw = get(url)
        txt = raw.decode("utf-8", "ignore")
        n_eid = len(set(re.findall(r'"eid":"([0-9a-f]{20,})"', txt)))
        n_mp3 = len(re.findall(r"media\.xyzcdn\.net", txt))
        extra = ""
        if check:
            extra = "  " + check(txt)
        print(f"  ✓ {label:34} {len(raw):>8}B  eid={n_eid:>3}  media={n_mp3:>3}{extra}")
        return txt
    except Exception as ex:
        print(f"  ✗ {label:34} {ex}")
        return None


def main():
    print("=" * 72)
    print("1. sitemap / robots")
    print("=" * 72)
    for u in [
        "https://www.xiaoyuzhoufm.com/robots.txt",
        "https://www.xiaoyuzhoufm.com/sitemap.xml",
        "https://www.xiaoyuzhoufm.com/sitemap_index.xml",
    ]:
        try_url(u.split("/")[-1], u)

    print()
    print("=" * 72)
    print("2. 其他页面形态")
    print("=" * 72)
    try_url("podcast/pid/episodes", f"https://www.xiaoyuzhoufm.com/podcast/{PID}/episodes")
    try_url("podcast/pid?tab=all", f"https://www.xiaoyuzhoufm.com/podcast/{PID}?tab=all")
    try_url("m 站", f"https://m.xiaoyuzhoufm.com/podcast/{PID}")
    try_url("分享页", f"https://www.xiaoyuzhoufm.com/podcast/{PID}/share")

    print()
    print("=" * 72)
    print("3. HTML 里的接口线索 / JS bundle")
    print("=" * 72)
    html = try_url("home", f"https://www.xiaoyuzhoufm.com/podcast/{PID}")
    if html:
        # 找 API 基址
        for pat in [r'https://api\.[a-z\.]+', r'"(/v1/[a-z\-/]+)"', r'buildId":"([^"]+)"',
                    r'"(https://[a-z0-9\.\-]+/_next/static/[^"]{10,80}\.js)"']:
            hits = sorted(set(re.findall(pat, html)))[:6]
            if hits:
                print(f"  {pat[:34]:36} {hits}")
        # 追问 hasMore / cursor
        for kw in ["hasMore", "nextCursor", "cursor", "loadMore"]:
            h = re.findall(rf'"{kw}"\s*:\s*([^,}}]{{1,24}})', html)
            if h:
                print(f"  {kw:14} {h[:4]}")

    print()
    print("=" * 72)
    print("4. Apple Podcasts 镜像（如果有，就有标准 RSS）")
    print("=" * 72)
    # iTunes 搜索
    q = urllib.parse.quote("眼哥股市会")
    try:
        raw = get(f"https://itunes.apple.com/search?term={q}&entity=podcast&limit=5")
        import json as _j

        data = _j.loads(raw)
        print(f"  iTunes 命中 {data.get('resultCount', 0)} 条")
        for r in data.get("results", [])[:5]:
            print(f"    {r.get('collectionName')}  |  {r.get('feedUrl')}")
    except Exception as ex:
        print(f"  ✗ iTunes 搜索失败 {ex}")


if __name__ == "__main__":
    import urllib.parse  # noqa: E402

    sys.exit(main())
