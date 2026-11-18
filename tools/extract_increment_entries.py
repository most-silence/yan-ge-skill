#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""extract_increment_entries.py — 把每桶未归并的增量条目切片到独立小文件

输出：_增量条目/{桶名}.md（只含增量段，agent 不用再读几千行的整桶文件）

阈值：默认读 research/_归并水位线.json 的 merged_through（已归并到的池内编号），
只提取比它新的条目；也可 `--from P####` 显式指定。避免把上一轮已归并的
P2612–P2735 重复提取一遍（那是增量归并最常见的重复劳动来源）。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
SRC = ROOT / "sources" / "05-播客转写" / "_分桶"
DST = ROOT / "sources" / "05-播客转写" / "_增量条目"
WATER = ROOT / "research" / "_归并水位线.json"
DST.mkdir(exist_ok=True)

MIN_PID = 2612
if "--from" in sys.argv:
    MIN_PID = int(sys.argv[sys.argv.index("--from")].lstrip("P"))
elif WATER.exists():
    try:
        MIN_PID = int(json.loads(WATER.read_text(encoding="utf-8"))["merged_through"]) + 1
    except Exception:
        pass
print(f"提取阈值：池内编号 >= P{MIN_PID:04d}")

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
        if m and int(m.group(1)) >= MIN_PID:
            inc.append(seg.rstrip() + "\n\n---\n\n")
    if not inc:
        continue
    out = DST / f.name
    head = (f"# 增量条目 · {f.stem}\n\n"
            f"> 仅含池内编号 P{MIN_PID:04d}+ 的候选（未归并增量），供增量归并用。"
            f"完整桶文件见 _分桶/{f.name}\n\n---\n\n")
    out.write_text(head + "".join(inc), encoding="utf-8")
    print(f"  {f.stem}: {len(inc)} 条 → {out.stat().st_size/1024:.0f} KB")
