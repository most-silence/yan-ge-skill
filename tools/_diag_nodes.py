#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_diag_nodes.py — 诊断 apply 脚本的节点匹配"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

bucket = "B07-空仓_不做"
NODE_RE = r"^###\s+(?:[A-Z]\d{2}-)?([A-Z]\d+(?:-[A-Z])?)\s*·"

t = (ROOT / "sources/05-播客转写/_归并" / f"{bucket}.md").read_text(encoding="utf-8")
heads = [m.group(1) for m in re.finditer(NODE_RE, t, re.M)]
headset = set(heads)

d = json.loads((ROOT / "research" / f"_merge_map_{bucket}.json").read_text(encoding="utf-8"))
items = d.get("items") or d.get("entries") or []

print(f"节点 {len(heads)} 个")
fails = [(e["cid"], e["target"]) for e in items
         if e.get("mode") == "merge" and e["target"] not in headset]
print(f"失败 {len(fails)} 条:")
for cid, tgt in fails:
    # 找 tgt 的近似节点
    cands = [h for h in headset if h.startswith(tgt[0]) and tgt[1:] in h]
    print(f"  {cid}→{tgt}  候选: {cands[:4]}")
