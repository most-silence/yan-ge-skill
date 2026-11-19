#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dump_unique_candidates.py — 导出全部待归并候选（按池编号去重）

同一条池内候选会落在多个桶（cids 不同），语义判断只需做一次。
输出 research/_待归并候选总表.md：每个池编号一段，列出
  - 池编号 / 全部 cid / 全部桶
  - 名字 / 触发 / 动作 / 数字 / 期次 / 时间戳 / 原话首句
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
INC = ROOT / "sources" / "05-播客转写" / "_增量条目"
MG = ROOT / "sources" / "05-播客转写" / "_归并"
OUT = ROOT / "research" / "_待归并候选总表.md"

LABELS = ["触发", "动作", "数字", "原话", "边界声明", "跨阶段", "备注"]


def field(body, label):
    m = re.search(r"\*\*" + label + r"\*\*[：:]?", body)
    if not m:
        return ""
    tail = body[m.end():]
    end = len(tail)
    for o in LABELS:
        if o == label:
            continue
        om = re.search(r"\*\*" + o + r"\*\*", tail)
        if om:
            end = min(end, om.start())
    return re.sub(r"\s+", " ", tail[:end]).strip().lstrip("-：:").strip()


by_pool = defaultdict(lambda: {"cids": [], "buckets": []})
info = {}

# 待归并的桶
todo = [f.stem for f in sorted(INC.glob("*.md"))
        if "第二轮增量" not in (MG / f.name).read_text(encoding="utf-8")]

for bucket in todo:
    t = (INC / f"{bucket}.md").read_text(encoding="utf-8")
    marks = [(m.start(), m.group(1)) for m in re.finditer(r"^## (B\d{2}-\d{3})", t, re.M)]
    for i, (pos, cid) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(t)
        body = t[pos:end]
        pid = re.search(r"\*\*P(\d{4})\*\*", body)
        pid = f"P{pid.group(1)}" if pid else cid
        name = re.search(r"^## B\d{2}-\d{3}\s*·\s*(.+)$", body, re.M)
        oid = re.search(r"期次\s*\|\s*`([A-Za-z0-9]{12,24})`", body)
        ts = re.search(r"`\[(\d{2}:\d{2}:\d{2})\]`", body)
        by_pool[pid]["cids"].append(cid)
        by_pool[pid]["buckets"].append(bucket.split("-")[0])
        if pid not in info:
            info[pid] = {
                "name": name.group(1).strip() if name else "",
                "trigger": field(body, "触发条件") or field(body, "触发"),
                "action": field(body, "动作"),
                "numbers": field(body, "具体数字") or field(body, "数字"),
                "oid": oid.group(1) if oid else "",
                "ts": ts.group(1) if ts else "",
            }

L = ["# 待归并候选总表（按池编号去重）", "",
     f"> 待归并桶 {len(todo)} 个：{'、'.join(b.split('-')[0] for b in todo)}",
     f"> 唯一候选 {len(by_pool)} 条（共 {sum(len(v['cids']) for v in by_pool.values())} 个桶位）", ""]
for pid in sorted(by_pool, key=lambda x: int(re.sub(r"\D", "", x) or 0)):
    v = by_pool[pid]
    i = info[pid]
    L += [f"## {pid} · {i['name'][:60]}", "",
          f"- 桶位: {'、'.join(f'{b}/{c}' for b, c in zip(v['buckets'], v['cids']))}",
          f"- 期次: `{i['oid']}` `[{i['ts']}]`",
          f"- 触发: {i['trigger'][:200]}",
          f"- 动作: {i['action'][:260]}",
          f"- 数字: {i['numbers'][:120]}", ""]
OUT.write_text("\n".join(L), encoding="utf-8")
print(f"待归并桶 {len(todo)} 个，唯一候选 {len(by_pool)} 条 → {OUT.name}")