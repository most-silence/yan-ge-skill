#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_js_api.py — 从小宇宙前端 JS 包里挖真实分页接口

背景：主页只嵌 15 集，api.xiaoyuzhoufm.com 裸调 401。
但网页自己能在滚动时加载后面的集数——说明密钥/签名就在前端包里。
这个脚本：抓首页引用的全部 JS chunk，正则搜出：
  · /v1/xxx/yyy 形态的接口路径
  · base URL
  · 可能的鉴权头字段名（authorization / x-app-*）
只报告事实，不硬编码调用。
"""
import re
import sys
import urllib.request

PID = "6860f13d09b4c8a7b539a3f8"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def get(u, t=25):
    req = urllib.request.Request(u, headers=UA)
    return urllib.request.urlopen(req, timeout=t).read().decode("utf-8", "ignore")


def main():
    html = get("https://www.xiaoyuzhoufm.com/podcast/" + PID)
    srcs = sorted(set(re.findall(r'src="([^"]+\.js)"', html)))
    print(f"首页引用 {len(srcs)} 个 JS chunk\n")

    all_paths = {}
    all_hosts = {}
    auth_fields = set()
    for s in srcs:
        name = s.rsplit("/", 1)[-1]
        try:
            js = get(s)
        except Exception as ex:
            print(f"  ✗ {name}: {type(ex).__name__}")
            continue
        paths = set()
        # 接口路径
        for m in re.findall(r'["\'](/v\d+/[a-zA-Z0-9_\-/]{3,60})["\']', js):
            paths.add(m)
        for m in re.findall(r'["\'](podcast/[a-zA-Z0-9_\-/]{2,50})["\']', js):
            paths.add(m)
        for m in re.findall(
            r'["\'](episode/[a-zA-Z0-9_\-/]{2,50})["\']', js
        ):
            paths.add(m)
        for m in re.findall(
            r'["\'](https?://[a-z0-9.\-]*xiaoyuzhoufm\.com[a-zA-Z0-9_\-./]*)["\']', js
        ):
            all_hosts[m] = all_hosts.get(m, 0) + 1
        # 鉴权字段线索
        for m in re.findall(r'["\']((?:x-[a-z\-]+|authorization))["\']', js, re.I):
            auth_fields.add(m.lower())
        hits = sorted(paths)
        if hits:
            print(f"  ✓ {name}  ({len(js)//1024}KB)")
            for h in hits:
                print(f"      {h}")
                all_paths[h] = all_paths.get(h, 0) + 1

    print("\n=== 主机名 ===")
    for h in sorted(all_hosts):
        print(f"  {h}")

    print("\n=== 疑似分页/列表接口 ===")
    key_pat = re.compile(
        r"(episode|podcast|list|page|cursor|feed|show)", re.I
    )
    for p in sorted(all_paths):
        star = "  ⭐" if key_pat.search(p) else ""
        print(f"  {p}{star}")

    print("\n=== 鉴权相关字段名 ===")
    interesting = sorted(
        f for f in auth_fields if f not in ("authorization",)
    )
    print("  authorization 出现:", "authorization" in auth_fields)
    for f in interesting[:40]:
        print(f"  {f}")


if __name__ == "__main__":
    sys.exit(main())
