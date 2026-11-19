#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dump_node_list.py — 把每个归并文件的节点编号+名字抽成小清单

映射 agent 只需读「增量条目 + 节点清单」两个小文件就能判定，
不必加载 100–200 KB 的完整归并文件（这是上一批映射 agent 慢的原因）。

输出：research/_节点清单_<桶名>.txt（每行「编号 · 名字」）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
MERGE = ROOT / "sources" / "05-播客转写" / "_归并"
OUT = ROOT / "research"

NODE_RE = re.compile(r"^#{3,4}\s+(?:[A-Z]\d{2}-)?([A-Z]\d+(?:-[A-Z])?)\s*·\s*(.+)$", re.M)

for f in sorted(MERGE.glob("*.md")):
    bucket = f.stem
    t = f.read_text(encoding="utf-8")
    nodes = [(m.group(1), m.group(2).strip()[:48]) for m in NODE_RE.finditer(t)]
    lines = [f"# 节点清单 · {bucket}（{len(nodes)} 个节点，供归并映射用）", ""]
    lines += [f"{nid} · {nm}" for nid, nm in nodes]
    (OUT / f"_节点清单_{bucket}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {bucket}: {len(nodes)} 节点")
