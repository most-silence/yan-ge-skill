#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_stat_increment.py — 统计第二轮增量的期次与规则（文件方式，避 here-string 转义）"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
INC = ROOT / "sources" / "05-播客转写" / "_增量条目"

BT = chr(96)
ids = set()
for f in INC.glob("*.md"):
    ids |= set(re.findall(r"期次\s*\|\s*" + BT + r"([A-Za-z0-9]{12,24})" + BT, f.read_text(encoding="utf-8")))
print(f"第二轮期次 id: {len(ids)} 个")
print("长度分布:", sorted(set(len(i) for i in ids)))
for i in sorted(ids)[:10]:
    print(" ", i)
