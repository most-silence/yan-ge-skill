#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""prepare_batches.py — 把 379 期清洗稿切成批读批次

为什么按行情阶段交错分组
------------------------
如果按日期顺序切批，一批全在 R1（强涨）、另一批全在 R6（急跌），
批读 subagent 的产出就会带上「这一段行情」的口径偏差，
汇总时又要把偏差消掉——等于制造问题再解决。

交错分组让**每一批内部都跨多个行情阶段**，subagent 在批内就能看到
同一条规则在涨跌两种环境下的不同表述。这也是「跨阶段复现」判定的前置条件。

输出
----
  sources/05-播客转写/_batches/batch-01.md ... batch-NN.md
  sources/05-播客转写/_batches/index.json

用法
----
  python tools/prepare_batches.py --size 10
"""

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = ROOT / "sources" / "05-播客转写" / "audio_txt"
REGIME_JSON = ROOT / "sources" / "05-播客转写" / "_行情阶段.json"
PRESCAN_JSON = ROOT / "sources" / "05-播客转写" / "_预筛地图.json"
OUT_DIR = ROOT / "sources" / "05-播客转写" / "_batches"

REGIME_NAME = {
    "R1": "主升强涨", "R2": "高位横盘", "R3": "冲高见顶", "R4": "第一波急跌",
    "R5": "反弹", "R6": "二次急跌", "R7": "反弹", "R8": "再下跌", "U": "无日期",
}


def build_path_index():
    """eid → 清洗稿路径

    不能靠 eid 直接拼文件名：标题里也可能有下划线，且部分期次清洗稿缺失。
    直接扫目录，从文件名第一个下划线前截 eid。
    """
    idx = {}
    for p in TXT_DIR.glob("*.txt"):
        if p.name.endswith("._clean.txt"):
            eid = p.name.split("_")[0]
            idx[eid] = p               # 清洗稿优先（后写覆盖）
    for p in TXT_DIR.glob("*.txt"):
        if not p.name.endswith("._clean.txt"):
            eid = p.name.split("_")[0]
            idx.setdefault(eid, p)     # 没有清洗稿才回退原稿
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=10, help="每批期数（默认 10）")
    args = ap.parse_args()

    reg = json.loads(REGIME_JSON.read_text(encoding="utf-8"))
    pre = json.loads(PRESCAN_JSON.read_text(encoding="utf-8"))
    paths = build_path_index()

    # eid → 阶段元信息
    meta = {}
    for e in reg["episodes"]:
        meta[e["eid"]] = {
            "title": e["title"], "date": e["date"], "regime": e["regime"],
            "dur_min": e["dur_min"],
        }
    for e in reg["undated"]:
        meta[e["eid"]] = {
            "title": e["title"], "date": "", "regime": "U", "dur_min": e["dur_min"],
        }

    # 按阶段分桶
    buckets = OrderedDict((k, []) for k in
                          ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "U"])
    for eid, m in meta.items():
        buckets.setdefault(m["regime"], []).append(eid)
    for k in buckets:
        # 桶内按日期排序，保证批内时间有序
        buckets[k].sort(key=lambda e: meta[e]["date"] or "9999")

    # 轮转交错：依次从每个桶取一个，拼成批
    order = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "U"]
    interleaved = []
    idx = {k: 0 for k in order}
    while True:
        took = False
        for k in order:
            if idx[k] < len(buckets.get(k, [])):
                interleaved.append(buckets[k][idx[k]])
                idx[k] += 1
                took = True
        if not took:
            break

    # 切批
    batches = [interleaved[i:i + args.size] for i in range(0, len(interleaved), args.size)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    index = []
    for bi, eids in enumerate(batches, 1):
        parts = []
        P = parts.append
        regimes_in = sorted({meta[e]["regime"] for e in eids})
        dates = sorted(meta[e]["date"] for e in eids if meta[e]["date"])

        P(f"# 批读批次 {bi:02d} / {len(batches):02d}")
        P("")
        P(f"> 本期数：**{len(eids)}** ｜ 行情阶段：**{'/'.join(regimes_in)}** "
          f"｜ 日期跨度：{dates[0] if dates else '—'} ~ {dates[-1] if dates else '—'}")
        P("> 本批内**故意跨多个行情阶段**——同一规则在涨跌环境下的不同表述要分别记录。")
        P("")
        P("---")
        P("")

        for k, eid in enumerate(eids, 1):
            m = meta[eid]
            p = paths.get(eid)
            if p is None or not p.exists():
                P(f"## {k}. {m['title']}")
                P("")
                P(f"> ⚠️ **转写稿缺失**（`{eid}`），本期跳过。")
                P("")
                continue
            body = p.read_text(encoding="utf-8", errors="ignore")
            # 去掉元信息头，只留正文（头部信息已在下方表格给出）
            if "\n---\n" in body:
                body = body.split("\n---\n", 1)[1]

            # 本期的预筛命中（只给 S/M 档，W 档太多会淹没）
            hits = (pre["episodes"].get(eid) or {}).get("hits") or []
            sm = [h for h in hits if h["tier"] in ("S", "M")]

            P(f"## {k}. {m['title']}")
            P("")
            P(f"| 项 | 值 |")
            P(f"|---|---|")
            P(f"| 期次 ID | `{eid}` |")
            P(f"| 发布日期 | {m['date'] or '（标题无日期）'} |")
            P(f"| 行情阶段 | **{m['regime']} {REGIME_NAME.get(m['regime'], '')}** |")
            P(f"| 音频时长 | {m['dur_min']} 分钟 |")
            P(f"| 预筛命中 | S×{sum(1 for h in hits if h['tier']=='S')} "
              f"/ M×{sum(1 for h in hits if h['tier']=='M')} "
              f"/ W×{sum(1 for h in hits if h['tier']=='W')} |")
            P("")
            if sm:
                P("**预筛高信号点**（这几处优先细看，但不是全部——规则常跨段）：")
                P("")
                for h in sm[:8]:
                    nums = "、".join(h["nums"][:3]) or "—"
                    P(f"- `{h['ts']}` 数字[{nums}] → {h['text'][:80]}")
                P("")
            P("**正文**")
            P("")
            P("```")
            P(body.strip())
            P("```")
            P("")
            P("---")
            P("")

        # 批尾：抽取指令
        P("## 抽取指令（必读）")
        P("")
        P("读完全部正文后，按下面的格式输出规则候选。**硬要求见 `_批读模板.md`。**")
        P("")
        P("输出文件：`sources/05-播客转写/_规则候选/batch-{:02d}.md`".format(bi))
        P("")

        f = OUT_DIR / f"batch-{bi:02d}.md"
        f.write_text("\n".join(parts) + "\n", encoding="utf-8")

        index.append({
            "batch": bi,
            "file": f"batch-{bi:02d}.md",
            "size_kb": round(f.stat().st_size / 1024),
            "episodes": eids,
            "regimes": regimes_in,
            "dates": [dates[0], dates[-1]] if dates else [],
        })

    (OUT_DIR / "index.json").write_text(
        json.dumps({"batch_size": args.size, "total_batches": len(batches),
                    "total_episodes": len(interleaved), "batches": index},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(interleaved)} 期 → {len(batches)} 批（每批 {args.size} 期）")
    for b in index:
        print(f"  {b['file']}  {b['size_kb']:>4} KB  "
              f"{len(b['episodes'])} 期  {'/'.join(b['regimes'])}")
    tot = sum(b["size_kb"] for b in index)
    print(f"\n合计 {tot / 1024:.1f} MB  ≈ {tot * 1024 / 3 / 1000:.0f}k tokens（中文按 3 字节/token）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
