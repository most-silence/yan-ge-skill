#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""cross_bucket_dedup.py — 跨桶去重分析

问题
----
26 个桶各自做了桶内归并，产出 1,264 个规则节点。但**桶是重叠的**：
一条候选平均落进 3.7 个桶（2,611 条候选 → 9,762 个桶内位置）。

所以同一条规则会在多个桶里各出现一次，名字还被各桶归并员改写成不同说法：

    B05/M04  禁止高位加仓与倒三角加仓
    B16/M09  禁止高位加仓与倒三角加仓      ← 这两个碰巧同名

但更多是这样：
    B12/M12  到什么点位打多少仓：分档仓位地图
    B21/M40  到什么点位打多少仓：分档仓位地图   ← 也碰巧同名

    B01/M05  破位即止损：技术位失守就走
    B06/M02  破位就减仓/清仓：越过技术位即处置   ← 名字不同，其实是同一件事的两面

完全同名只有 3 组，说明**用名字判重会严重漏判**。

怎么判
------
用「触发条件 + 动作」的正文相似度。这两段是规则的实质，
名字只是标签——不同归并员给同一规则起不同名字很正常，但触发和动作会高度重合。

输出
----
  _跨桶重复.json   候选重复组（供人工确认）
  _跨桶重复.md     可读报告

注意：这只是**候选**。相似不等于同一——两个桶从不同角度看同一规则时，
可能侧重不同的面（止损桶看「什么时候走」，减仓桶看「走多少」）。
真正的合并要人工确认或交给下一层归并。
"""

import json
import re
import sys
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MERGE_DIR = ROOT / "sources" / "05-播客转写" / "_归并"
OUT_JSON = ROOT / "sources" / "05-播客转写" / "_跨桶重复.json"
OUT_MD = ROOT / "sources" / "05-播客转写" / "_跨桶重复.md"

HDR_RE = re.compile(r"^#{3,4}\s+([A-Z]\d*[-M\d]*[A-Z]?)\s*[·.]\s*(.+)$", re.M)

# 字段标签全表——用来划定字段边界
FIELD_LABELS = [
    "触发条件", "动作", "具体数字", "原话", "要素完备度", "我的判断",
    "跨阶段证据", "归入了", "归入了哪些候选", "备注", "代表原话",
    "冲突标记", "为什么是 reference 不是 verified", "缺什么", "补读线索",
]


def extract_field(body, label):
    """抽出某个字段的正文

    ⚠️ 这个坑踩过三次了（merge_candidates、spotcheck、这里）：
    批读/归并产出的字段排版不统一，同一个字段有四种写法：

        - **触发条件**：任何一次买入之前。        ← 列表项 + 同行内容
        **触发条件**（什么情况下用）：           ← 标签带括注、内容在下一行
        **触发条件**：内容                       ← 标签 + 同行
        **触发条件**：
        跨行内容                                  ← 内容跨多行

    一个 `\\*\\*标签\\*\\*[^\\n]*\\n?(.+)` 正则会在前两种写法上翻车：
    `[^\\n]*` 先把**同行的内容**吃光，`\\n?` 跳到下一行，
    于是 `(.+)` 抓到的是**下一个字段**的内容——整条链错位一格。

    正确做法：定位标签 → 跳过括注与冒号 → 抓到**下一个字段标签**为止。
    """
    m = re.search(r"\*\*" + re.escape(label) + r"\*\*", body)
    if not m:
        return ""
    start = m.end()
    rest = body[start:]
    skip = re.match(r"[^\n：:]{0,30}[：:]\s*", rest)
    if skip:
        start += skip.end()
    end = len(body)
    tail = body[start:]
    for other in FIELD_LABELS:
        if other == label:
            continue
        om = re.search(r"\*\*" + re.escape(other) + r"\*\*", tail)
        if om and start + om.start() < end:
            end = start + om.start()
    seg = body[start:end]
    return re.sub(r"\s+", " ", seg).strip().lstrip("-").strip()


def load_nodes():
    """读出所有规则节点：(桶, 编号, 名字, 触发, 动作, 数字, 引文, 跨阶段)"""
    nodes = []
    for f in sorted(MERGE_DIR.glob("*.md")):
        bucket = f.stem.split("-")[0]
        text = f.read_text(encoding="utf-8")
        i = text.find("## 二、")
        j = re.search(r"^## [三四]、", text[i:], re.M)
        seg = text[i:i + j.start()] if (i >= 0 and j) else text

        marks = [(m.start(), m.group(1), m.group(2).strip())
                 for m in HDR_RE.finditer(seg)]
        for k, (pos, rid, name) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else len(seg)
            body = seg[pos:end]

            nodes.append({
                "bucket": bucket,
                "id": rid,
                "name": name,
                "trigger": extract_field(body, "触发条件"),
                "action": extract_field(body, "动作"),
                "numbers": extract_field(body, "具体数字"),
                "has_quote": ">" in body,
                "full_id": f"{bucket}/{rid}",
            })
    return nodes


def substance(n):
    """规则的实质文本：触发 + 动作

    不含名字——名字是标签，不同归并员对同一规则会给不同名字。
    不含数字——数字是同一规则的宽窄变体。
    """
    return (n["trigger"] + " " + n["action"]).strip()


def sim(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def main():
    nodes = load_nodes()
    print(f"读入 {len(nodes)} 个规则节点（{len(set(n['bucket'] for n in nodes))} 个桶）")

    # 只跨桶比较：同桶内的归并已经做完了
    pairs = []
    by_bucket = {}
    for n in nodes:
        by_bucket.setdefault(n["bucket"], []).append(n)

    bl = sorted(by_bucket)
    print(f"跨桶两两比较 {len(bl)*(len(bl)-1)//2} 个桶对…")
    for i in range(len(bl)):
        for j in range(i + 1, len(bl)):
            A, B = by_bucket[bl[i]], by_bucket[bl[j]]
            for a in A:
                sa = substance(a)
                if len(sa) < 12:
                    continue
                for b in B:
                    sb = substance(b)
                    if len(sb) < 12:
                        continue
                    s = sim(sa, sb)
                    if s >= 0.55:
                        pairs.append((s, a, b))

    pairs.sort(key=lambda x: -x[0])

    # ── 把高相似对连成组（简单并查集）──
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    by_id = {n["full_id"]: n for n in nodes}
    for s, a, b in pairs:
        union(a["full_id"], b["full_id"])

    groups = {}
    for n in nodes:
        r = find(n["full_id"])
        groups.setdefault(r, []).append(n)

    dup_groups = [g for g in groups.values() if len(g) > 1]
    dup_groups.sort(key=lambda g: -len(g))

    # 只有 6 个以上桶都出现的才算「核心规则」
    core = [g for g in dup_groups if len(set(n["bucket"] for n in g)) >= 6]

    print(f"\n相似对（≥0.55）：{len(pairs)}")
    print(f"重复组：{len(dup_groups)} 组，涉及 {sum(len(g) for g in dup_groups)} 个节点")
    print(f"其中跨 ≥6 个桶的：{len(core)} 组")
    print(f"\n单体规则（只出现在 1 个桶）：{len([g for g in groups.values() if len(g)==1])} 个")

    OUT_JSON.write_text(json.dumps({
        "nodes_total": len(nodes),
        "pairs": len(pairs),
        "dup_groups": len(dup_groups),
        "core_groups": len(core),
        "groups": [
            {
                "size": len(g),
                "buckets": sorted(set(n["bucket"] for n in g)),
                "members": [{"id": n["full_id"], "name": n["name"],
                             "trigger": n["trigger"][:120], "action": n["action"][:120]}
                            for n in g],
            } for g in dup_groups
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    L = []
    A = L.append
    A("# 线3 播客 · 跨桶去重分析")
    A("")
    A("> 生成：2026-11-02 ｜ 工具：`tools/cross_bucket_dedup.py`")
    A("")
    A("## 为什么会有跨桶重复")
    A("")
    A("26 个桶各自做了桶内归并，产出 1,264 个规则节点。但**桶是重叠的**：")
    A("一条候选平均落进 3.7 个桶（2,611 条候选 → 9,762 个桶内位置）。")
    A("")
    A("所以同一条规则会在多个桶里各出现一次，名字还被各桶归并员改写成不同说法。")
    A("")
    A("**完全同名只有 3 组**——说明用名字判重会严重漏判。")
    A("所以这里用「触发条件 + 动作」的正文相似度：这两段是规则的实质，")
    A("名字只是标签（不同归并员对同一规则会给不同名字），数字是同一条的宽窄变体。")
    A("")
    A("## 结果")
    A("")
    A("| 项 | 值 |")
    A("|---|---|")
    A(f"| 规则节点总数 | {len(nodes)} |")
    A(f"| 相似对（≥0.55） | {len(pairs)} |")
    A(f"| 重复组 | {len(dup_groups)} 组 |")
    A(f"| 涉及节点 | {sum(len(g) for g in dup_groups)} |")
    A(f"| 跨 ≥6 桶的核心规则 | {len(core)} 组 |")
    A(f"| 单体规则（只在 1 个桶） | {len([g for g in groups.values() if len(g)==1])} |")
    A("")
    A("> **⚠️ 这只是候选，不是结论。** 相似不等于同一——")
    A("> 两个桶从不同角度看同一规则时可能侧重不同面")
    A(">（止损桶看「什么时候走」，减仓桶看「走多少」）。")
    A("> 真正的合并要人工确认或交给下一层归并。")
    A("")
    A("---")
    A("")
    A("## 一、核心规则（跨 ≥6 个桶，最可信）")
    A("")
    for gi, g in enumerate(core, 1):
        buckets = sorted(set(n["bucket"] for n in g))
        names = sorted(set(n["name"] for n in g))
        A(f"### C{gi:02d} · 跨 {len(buckets)} 桶 ｜ {len(g)} 个节点")
        A("")
        A(f"**桶**：{'、'.join(buckets)}")
        A("")
        A("**各桶的叫法**：")
        A("")
        for nm in names[:6]:
            A(f"- {nm}")
        A("")
        A("**最完整的触发+动作**：")
        A("")
        best = max(g, key=lambda n: len(substance(n)))
        A(f"- 触发：{best['trigger'][:200]}")
        A(f"- 动作：{best['action'][:200]}")
        A("")
    A("---")
    A("")
    A("## 二、其余重复组（2–5 个桶）")
    A("")
    A("| 组 | 桶数 | 节点 | 叫法 |")
    A("|---|---:|---:|---|")
    for gi, g in enumerate([x for x in dup_groups if x not in core], 1):
        buckets = sorted(set(n["bucket"] for n in g))
        names = sorted(set(n["name"] for n in g))
        A(f"| G{gi:03d} | {len(buckets)} | {len(g)} | {'、'.join(buckets)} ｜ {names[0][:44]} |")
    A("")
    A("---")
    A("")
    A("## 三、下一步")
    A("")
    A("跨桶去重完成后，剩下的**真正唯一规则**才是 SKILL 的零件。")
    A("之后把这些零件按「心智模型」组装——顺序不能反：")
    A("心智模型是归并的产出，不能当输入。")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    print(f"→ {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())