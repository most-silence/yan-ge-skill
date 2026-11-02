# -*- coding: utf-8 -*-
"""独立复核：产出里每个引文块，逐行确认「该时间戳在原文是否就是这句话」。
verify_quotes.py 只校验片段是否出现在全文（可能串行），这一步校验时间戳对位。"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TX = ROOT / "sources" / "05-播客转写" / "audio_txt"
CAND = ROOT / "sources" / "05-播客转写" / "_规则候选" / "batch-34.md"

SRC = {}
for p in TX.glob("*._clean.txt"):
    eid = p.name.split("_")[0]
    d = {}
    for m in re.finditer(r"^\[(\d{2}:\d{2}:\d{2})\] (.*)$", p.read_text(encoding="utf-8"), re.M):
        d.setdefault(m.group(1), []).append(m.group(2))
    SRC[eid] = d

text = CAND.read_text(encoding="utf-8")
blocks = re.findall(r"((?:^> \[\d{2}:\d{2}:\d{2}\].*\n)+)\s*\n—— `([A-Za-z0-9]+)` `\[(\d{2}:\d{2}:\d{2})\]`~`\[(\d{2}:\d{2}:\d{2})\]`", text, re.M)
print("块数", len(blocks))
bad = 0
for body, eid, t1, t2 in blocks:
    rows = re.findall(r"^> \[(\d{2}:\d{2}:\d{2})\] (.*)$", body, re.M)
    if rows[0][0] != t1 or rows[-1][0] != t2:
        print("!! 范围标注与块内首尾不一致", eid, t1, t2, rows[0][0], rows[-1][0]); bad += 1
    if eid not in SRC:
        print("!! 期次不存在", eid); bad += 1; continue
    for ts, line in rows:
        if ts not in SRC[eid]:
            print("!! 时间戳不存在", eid, ts); bad += 1; continue
        if line not in SRC[eid][ts]:
            print("!! 该时间戳原文不是这句", eid, ts)
            print("   产出:", line[:110])
            print("   原文:", SRC[eid][ts][0][:110]); bad += 1
print("不一致行数", bad)
