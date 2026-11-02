#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""rule_digest.py — 生成分组规则摘要，供组装心智模型用

为什么要摘要
------------
归并产出总计约 3 MB（26 个桶，含大量引文）。直接交给 subagent 读，
上下文放不下，且大量引文对「组装心智模型」这个任务是噪音——
组装要的是「他怎么看」，不是逐字证据（引文在需要核实时再回原文件取）。

所以生成摘要：每条规则一行，带名字 + 触发 + 动作 + 跨阶段数。
一个分组几万字符，subagent 能完整读完。

分组
----
按「看图 / 量价 / 位置 / 仓位 / 风控 / 时间心性」六组，
每组 3–5 个主题桶。分组是给组装阶段用的中间层——
心智模型是跨主题的，所以不能一个桶一个模型。

用法
----
  python tools/rule_digest.py
  python tools/rule_digest.py --group G1
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MERGE_DIR = ROOT / "sources" / "05-播客转写" / "_归并"
OUT_DIR = ROOT / "sources" / "05-播客转写" / "_摘要"

# 六组：每组 3–5 个桶。心智模型跨主题，所以分组比桶粗、比全体细。
GROUPS = [
    ("G1", "技术看图", ["B08-均线系统", "B19-多周期确认", "B11-形态_结构", "B10-压力支撑"],
     "他怎么读图：均线、周期、形态、关键位"),
    ("G2", "量价与资金", ["B09-量能", "B21-资金_主力", "B17-板块_轮动"],
     "量能验证、主力动向、板块轮动"),
    ("G3", "位置判断", ["B12-底部判断", "B13-顶部判断", "B16-追涨_位置感", "B18-大盘_指数"],
     "高低位、底部顶部、指数"),
    ("G4", "仓位管理", ["B03-仓位分层", "B04-建仓", "B05-加仓_补仓", "B06-减仓_清仓", "B07-空仓_不做"],
     "几成仓、怎么加怎么减、什么时候不做"),
    ("G5", "风控与兑现", ["B01-止损", "B02-止盈", "B14-反弹", "B15-做T"],
     "认错离场、兑现利润、反弹处理、日内短差"),
    ("G6", "时间心性与宏观", ["B22-时间窗_日历", "B23-概率_胜率", "B20-纪律_心态", "B24-宏观_外围", "X-未分桶"],
     "时间窗、胜率账、纪律心态、宏观外围"),
]

FIELD_LABELS = [
    "触发条件", "动作", "具体数字", "原话", "要素完备度", "我的判断",
    "跨阶段证据", "归入了", "归入了哪些候选", "备注", "代表原话",
    "冲突标记", "为什么是 reference 不是 verified", "缺什么", "补读线索",
]


def extract_field(body, label):
    """抽字段正文（同 merge_candidates.py 的修法，见那里的注释）"""
    m = re.search(r"\*\*" + re.escape(label) + r"\*\*", body)
    if not m:
        return ""
    start = m.end()
    skip = re.match(r"[^\n：:]{0,30}[：:]\s*", body[start:])
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
    return re.sub(r"\s+", " ", body[start:end]).strip().lstrip("-").strip()


def load_nodes(bucket_stem):
    """读一个桶的归并产出，返回规则节点列表"""
    f = MERGE_DIR / f"{bucket_stem}.md"
    if not f.exists():
        return []
    text = f.read_text(encoding="utf-8")
    i = text.find("## 二、")
    j = re.search(r"^## [三四]、", text[i:], re.M)
    seg = text[i:i + j.start()] if (i >= 0 and j) else text

    marks = [(m.start(), m.group(1), m.group(2).strip())
             for m in re.finditer(r"^#{3,4}\s+([A-Z]\d*[-M\d]*[A-Z]?)\s*[·.]\s*(.+)$", seg, re.M)]
    out = []
    for k, (pos, rid, name) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(seg)
        body = seg[pos:end]
        ev = extract_field(body, "跨阶段证据")
        m = re.search(r"共\s*(\d+)\s*期", ev)
        n_ep = int(m.group(1)) if m else 0
        out.append({
            "id": rid, "name": name,
            "trigger": extract_field(body, "触发条件"),
            "action": extract_field(body, "动作"),
            "numbers": extract_field(body, "具体数字"),
            "evidence": ev,
            "n_ep": n_ep,
            "conflict": extract_field(body, "冲突标记") or extract_field(body, "备注"),
            "is_leaf": bool(re.search(r"-[A-Z]$", rid)),
            "is_single": bool(re.fullmatch(r"S\d+(?:-[A-Z])?", rid)),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default=None, help="只生成某个组，如 G1")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    groups = [g for g in GROUPS if not args.group or g[0] == args.group]

    index = []
    for code, gname, buckets, desc in groups:
        all_nodes = []
        for b in buckets:
            nodes = load_nodes(b)
            for n in nodes:
                n["bucket"] = b
            all_nodes.extend(nodes)

        # 排序：跨期次多的优先（证据强的先看）
        all_nodes.sort(key=lambda n: (-n["n_ep"], n["id"]))

        L = []
        A = L.append
        A(f"# 规则摘要 · {code} {gname}")
        A("")
        A(f"> 主题：{desc}")
        A(f"> 来源桶：{'、'.join(buckets)}")
        A(f"> 规则节点：**{len(all_nodes)}** 条 ｜ 工具：`tools/rule_digest.py`")
        A("")
        A("## 怎么用这份摘要")
        A("")
        A("- 每行格式：`编号 · 名字`，下挂「触发」「动作」「跨阶段」三项")
        A("- **跨阶段（N 期）越大，证据越强**——N≥8 的通常是他的核心方法；N=1 的可能是偶发说法")
        A("- 编号说明：`M` = 归并出的规则，`S` = 单列（无法归并），`-A/-B` 后缀 = 子规则")
        A("- 需要逐字原话时，回 `_归并/{桶名}.md` 取，摘要里不带引文")
        A("")
        A("---")
        A("")

        for n in all_nodes:
            tag = ""
            if n["is_single"]:
                tag = " 〔单列〕"
            elif n["is_leaf"]:
                tag = " 〔子规则〕"
            A(f"### {n['bucket'].split('-')[0]}/{n['id']} · {n['name']}{tag}")
            A("")
            if n["trigger"]:
                A(f"- **触发**：{n['trigger'][:400]}")
            if n["action"]:
                A(f"- **动作**：{n['action'][:400]}")
            if n["numbers"]:
                A(f"- **数字**：{n['numbers'][:250]}")
            if n["evidence"]:
                A(f"- **跨阶段**：{n['evidence'][:200]}")
            if n["conflict"]:
                A(f"- **备注**：{n['conflict'][:250]}")
            A("")

        text = "\n".join(L)
        f = OUT_DIR / f"{code}-{gname}.md"
        f.write_text(text + "\n", encoding="utf-8")
        index.append({
            "code": code, "name": gname, "buckets": buckets,
            "rules": len(all_nodes),
            "kb": round(f.stat().st_size / 1024),
            "chars": len(text),
            "file": f.name, "desc": desc,
        })
        print(f"  {code} {gname:<10} {len(all_nodes):>4} 条规则  "
              f"{f.stat().st_size/1024:>6.0f} KB  {len(text):>7,} 字符")

    (OUT_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    tot = sum(x["rules"] for x in index)
    print(f"\n合计 {tot} 条规则节点（含跨组重复）")
    print(f"→ {OUT_DIR.relative_to(ROOT)}\\")
    return 0


if __name__ == "__main__":
    sys.exit(main())