#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""extract_increment_entries.py — 把每桶 P2612+ 的增量条目切片到独立小文件

输出：_增量条目/{桶名}.md（只含增量段，agent 不用再读几千行的整桶文件）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
SRC = ROOT / "sources" / "05-播客转写" / "_分桶"
DST = ROOT / "sources" / "05-播客转写" / "_增量条目"
DST.mkdir(exist_ok=True)

HDR = re.compile(r"^##\s+([A-Z]\d{2}-\d{3}|[A-Z]\d{3,4})\s*[·.]", re.M)
PID = re.compile(r"\*\*P(\d{4})\*\*")

for f in sorted(SRC.glob("*.md")):
    t = f.read_text(encoding="utf-8")
    marks = [(m.start(), m.group(1)) for m in HDR.finditer(t)]
    inc = []
    for i, (pos, cid) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(t)
        seg = t[pos:end]
        m = PID.search(seg)
        if m and int(m.group(1)) >= 2612:
            inc.append(seg.rstrip() + "\n\n---\n\n")
    if not inc:
        continue
    out = DST / f.name
    head = (f"# 增量条目 · {f.stem}\n\n"
            f"> 仅含池内编号 P2612+ 的候选（batch-96/97/98），供增量归并用。"
            f"完整桶文件见 _分桶/{f.name}\n\n---\n\n")
    out.write_text(head + "".join(inc), encoding="utf-8")
    print(f"  {f.stem}: {len(inc)} 条 → {out.stat().st_size/1024:.0f} KB")
