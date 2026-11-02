"""update_xyz_new.py — 把小宇宙新增单集并入素材库并下载。

背景：earsonme 清单最新到 2026-09-30，小宇宙已更新到 2026-10-28，
缺口 15 集（379 - 364 = 15，与小宇宙首页条数吻合）。

流程：
  1. 读 _xyz_new15.json（小宇宙首页解析结果）
  2. 并入 urls.json（eid -> m4a 直链）
  3. 并入 全量清单.json（补 short / rel / 日期字段，标注来源）
  4. 下载音频到 audio/（断点续传，已存在则跳过）
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(r"E:\AIProjetct\Nothing\眼哥\sources\00-原始素材\earsonme")
TOOL = Path(r"E:\AIProjetct\Nothing\眼哥\tools")
DEST = BASE / "audio"
UA = {"User-Agent": "Mozilla/5.0"}
GOOD = re.compile(r"^https://media\.xyzcdn\.net/[A-Za-z0-9_\-]+/[A-Za-z0-9_\-]+\.m4a$")


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def save(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def safe(s):
    return re.sub(r'[\\/:*?"<>|]', "_", s or "").strip()


def main():
    new = load(TOOL / "_xyz_new15.json", [])
    if not new:
        print("没有新单集数据")
        return
    urls = load(BASE / "urls.json", {})
    rows = load(BASE / "全量清单.json", [])
    have = {r["eid"] for r in rows}

    added = []
    for e in new:
        u = e.get("url") or ""
        if not GOOD.match(u):
            print(f"  跳过（直链非法）: {e['title']}")
            continue
        urls[e["eid"]] = u
        if e["eid"] not in have:
            pub = (e.get("pub") or "")[:10]
            y, m, d = (int(x) for x in pub.split("-")) if pub.count("-") == 2 else (None, None, None)
            rows.append({
                "eid": e["eid"], "short": e["title"], "plays": None,
                "dur": e.get("dur"), "rel": pub,
                "Y": y, "M": m, "D": d, "src": "xiaoyuzhou",
            })
            added.append(e)
    save(BASE / "urls.json", urls)
    save(BASE / "全量清单.json", rows)
    print(f"并入直链 {len(new)} 条，清单新增 {len(added)} 条，总计 {len(urls)} 条直链 / {len(rows)} 条清单")

    # 下载
    ok = fail = 0
    for e in new:
        u = urls.get(e["eid"])
        if not u:
            continue
        path = DEST / f"{e['eid']}_{safe(e['title'])[:60]}.m4a"
        if path.exists() and path.stat().st_size > 100_000:
            print(f"  已存在 {path.name[:50]}")
            ok += 1
            continue
        try:
            req = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r, open(path, "wb") as f:
                n = 0
                while True:
                    c = r.read(1 << 16)
                    if not c:
                        break
                    f.write(c)
                    n += len(c)
            print(f"  ↓ {path.name[:50]}  {n/1e6:.1f}MB")
            ok += 1
        except Exception as ex:
            print(f"  ✗ {e['title'][:30]}  {type(ex).__name__}: {ex}")
            fail += 1
        time.sleep(0.5)
    print(f"下载完成：成功 {ok}，失败 {fail}")


if __name__ == "__main__":
    main()
