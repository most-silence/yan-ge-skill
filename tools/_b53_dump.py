#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dump batch-53 指定行区间，用于确认引文边界"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATCH = ROOT / "sources" / "05-播客转写" / "_batches" / "batch-53.md"
LINE_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] (.*)$")
HDR_RE = re.compile(r"^## (\d)\. ")

eps, ep = {}, None
for ln in BATCH.read_text(encoding="utf-8").splitlines():
    m = HDR_RE.match(ln)
    if m:
        ep = int(m.group(1)); eps[ep] = []
        continue
    if ep is None:
        continue
    m2 = LINE_RE.match(ln)
    if m2:
        eps[ep].append((m2.group(1), m2.group(2)))

for arg in sys.argv[1:]:
    e_s, t1, t2 = arg.split(",")
    e = int(e_s)
    print(f"===== ep{e} {t1}~{t2} =====")
    for t, s in eps[e]:
        if t1 <= t <= t2:
            print(f"> [{t}] {s}")
    print()
