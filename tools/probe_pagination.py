#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_pagination.py — 摸清小宇宙的翻页方式

已知：
  · 播客主页 HTML 里嵌着完整剧集 JSON（enclosure.url 是音频直链）
  · 一页只出 15 集，但总共 376 集
  · api.xiaoyuzhoufm.com 返回 401

要解决：怎么拿到全部 376 集。
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "ignore")


def summarize(label, html):
    eids = re.findall(r'"eid":"([0-9a-f]{20,})"', html)
    titles = re.findall(r'"title":"([^"]{2,40})"', html)
    dates = re.findall(r'"pubDate":"([^"]{10})', html)
    print(f"  {label:14} HTML={len(html):>7}  eid={len(eids):>3}  date={len(dates):>3}")
    if dates:
        print(f"                 日期 {min(dates)} ~ {max(dates)}")
    if titles:
        print(f"                 标题样例 {titles[0][:28]} … {titles[-1][:28]}")
    return eids


def main():
    print("=" * 70)
    print("一、page 参数是否真的翻页")
    print("=" * 70)
    seen = {}
    for q in ["", "?page=1", "?page=2", "?page=3", "?page=5"]:
        url = f"https://www.xiaoyuzhoufm.com/podcast/{PID}{q}"
        try:
            h = get(url)
            eids = summarize(q or "(无参)", h)
            seen[q or "(无参)"] = set(eids)
        except Exception as ex:
            print(f"  {q:14} 失败 {ex}")
    # 比较重叠
    keys = list(seen)
    if len(keys) >= 2:
        base = seen[keys[0]]
        print("\n  与首屏的 eid 重叠：")
        for k in keys[1:]:
            inter = len(base & seen[k])
            print(f"    {k:12} 重合 {inter}/{len(seen[k])}")

    print()
    print("=" * 70)
    print("二、RSS / 其他入口")
    print("=" * 70)
    for u in [
        f"https://www.xiaoyuzhoufm.com/feed/{PID}",
        f"https://www.xiaoyuzhoufm.com/podcast/{PID}/rss",
        f"https://rss.xiaoyuzhoufm.com/{PID}",
    ]:
        try:
            h = get(u)
            is_xml = h.lstrip().startswith("<?xml")
            print(f"  {u[:60]:60} {len(h):>7} 字 XML={is_xml}")
            if is_xml:
                n = len(re.findall(r"<enclosure", h))
                print(f"       enclosure {n} 条")
        except Exception as ex:
            print(f"  {u[:60]:60} 失败 {ex}")

    print()
    print("=" * 70)
    print("三、HTML 里有没有「总数 / 已加载」这类分页线索")
    print("=" * 70)
    try:
        h = get(f"https://www.xiaoyuzhoufm.com/podcast/{PID}")
        for kw in ["episodeCount", "totalCount", "hasMore", "nextCursor",
                   "loadMore", "pageSize", "offset", "limit"]:
            hits = re.findall(rf'"{kw}"\s*:\s*([^,}}]{{1,20}})', h)
            if hits:
                print(f"  {kw:14} {hits[:5]}")
    except Exception as ex:
        print(f"  失败 {ex}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
