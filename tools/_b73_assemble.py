#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch-73 拼装器：把模板里的 {{标签}} 换成从清洗稿原样取出的**连续行**。

存在理由：人工重打引文一定会在标点/口误处走形（v1 那 61 条错引文都是这么来的）。
这里只做一件事——按 (eid, 起时间戳, 止时间戳) 取连续行，一字不改地输出。

用法：python tools/_b73_assemble.py
"""
import glob
import re
import sys
from pathlib import Path

ROOT = Path(r"E:\AIProjetct\Nothing\眼哥")
TXT = ROOT / "sources" / "05-播客转写" / "audio_txt"
TPL = ROOT / "tools" / "_b73_tpl.md"
OUT = ROOT / "sources" / "05-播客转写" / "_规则候选" / "batch-73.md"

# 标签 -> (eid, 起 ts, 止 ts)。窗口必须是清洗稿里真实存在的行边界。
SPEC = {
    # ── 期1 uLQajekvrbth 2026-07-03 R6 二次急跌
    "A1": ("uLQajekvrbth", "00:00:38", "00:00:53"),
    "A2": ("uLQajekvrbth", "00:02:13", "00:02:24"),
    "A3": ("uLQajekvrbth", "00:02:29", "00:02:45"),
    "A4": ("uLQajekvrbth", "00:03:02", "00:03:09"),
    "A5": ("uLQajekvrbth", "00:03:17", "00:03:27"),
    "B1": ("uLQajekvrbth", "00:04:11", "00:04:16"),
    "B2": ("uLQajekvrbth", "00:06:08", "00:06:17"),
    "B3": ("uLQajekvrbth", "00:06:38", "00:06:43"),
    "B4": ("uLQajekvrbth", "00:07:10", "00:07:17"),
    "C2": ("uLQajekvrbth", "00:00:31", "00:00:34"),
    "C3": ("uLQajekvrbth", "00:02:50", "00:02:56"),
    "C4": ("uLQajekvrbth", "00:00:06", "00:00:06"),
    # ── 期2 GH0XxuW3UuxA 无日期 U
    "A6": ("GH0XxuW3UuxA", "00:03:59", "00:04:15"),
    "A7": ("GH0XxuW3UuxA", "00:18:53", "00:19:07"),
    "A8": ("GH0XxuW3UuxA", "00:06:39", "00:06:45"),
    "A9": ("GH0XxuW3UuxA", "00:07:01", "00:07:40"),
    "A10": ("GH0XxuW3UuxA", "00:10:05", "00:10:30"),
    "A11": ("GH0XxuW3UuxA", "00:11:35", "00:11:52"),
    "A12": ("GH0XxuW3UuxA", "00:13:21", "00:13:52"),
    "A13": ("GH0XxuW3UuxA", "00:15:40", "00:15:56"),
    "A14": ("GH0XxuW3UuxA", "00:20:10", "00:20:21"),
    "A15": ("GH0XxuW3UuxA", "00:24:32", "00:24:50"),
    "A16": ("GH0XxuW3UuxA", "00:25:44", "00:26:03"),
    "A17": ("GH0XxuW3UuxA", "00:26:07", "00:26:22"),
    "A18": ("GH0XxuW3UuxA", "00:27:07", "00:27:25"),
    "A19": ("GH0XxuW3UuxA", "00:27:58", "00:28:18"),
    "B5": ("GH0XxuW3UuxA", "00:14:43", "00:15:04"),
    "B6": ("GH0XxuW3UuxA", "00:23:35", "00:23:43"),
    "B7": ("GH0XxuW3UuxA", "00:25:24", "00:25:33"),
    "B8": ("GH0XxuW3UuxA", "00:24:52", "00:25:16"),
    "C1": ("GH0XxuW3UuxA", "00:32:22", "00:32:33"),
    # ── 期3 pHjytAlrXCYL 2025-08-26 R1 主升强涨
    "A20": ("pHjytAlrXCYL", "00:02:16", "00:02:48"),
    "A21": ("pHjytAlrXCYL", "00:03:01", "00:03:07"),
    "A22": ("pHjytAlrXCYL", "00:03:14", "00:04:02"),
    "A23": ("pHjytAlrXCYL", "00:14:47", "00:15:08"),
    "A24": ("pHjytAlrXCYL", "00:09:02", "00:09:22"),
    "A25": ("pHjytAlrXCYL", "00:07:50", "00:08:03"),
    "A26": ("pHjytAlrXCYL", "00:17:20", "00:18:01"),
    "A27": ("pHjytAlrXCYL", "00:16:47", "00:17:03"),
    "B9": ("pHjytAlrXCYL", "00:11:04", "00:11:16"),
    "B10": ("pHjytAlrXCYL", "00:14:39", "00:14:47"),
    # ── 期4 Iq9bE8gZf5w5 2025-11-07 R2 高位横盘
    "A28": ("Iq9bE8gZf5w5", "00:23:47", "00:23:59"),
    "A29": ("Iq9bE8gZf5w5", "00:15:52", "00:15:53"),
    "A30": ("Iq9bE8gZf5w5", "00:23:31", "00:23:40"),
    "A31": ("Iq9bE8gZf5w5", "00:10:52", "00:11:32"),
    "B11": ("Iq9bE8gZf5w5", "00:22:45", "00:22:50"),
    "B12": ("Iq9bE8gZf5w5", "00:17:57", "00:18:30"),
    "B13": ("Iq9bE8gZf5w5", "00:09:11", "00:09:16"),
    "B14": ("Iq9bE8gZf5w5", "00:21:16", "00:21:28"),
    "C5": ("Iq9bE8gZf5w5", "00:07:10", "00:07:25"),
}

_cache = {}


def body(eid):
    if eid in _cache:
        return _cache[eid]
    hits = glob.glob(str(TXT / f"{eid}_*._clean.txt"))
    if len(hits) != 1:
        sys.exit(f"清洗稿匹配异常：{eid} -> {hits}")
    lines = Path(hits[0]).read_text(encoding="utf-8", errors="ignore").splitlines()
    try:
        i = lines.index("---")
    except ValueError:
        sys.exit(f"{eid} 找不到 --- 分隔线")
    _cache[eid] = [ln.rstrip() for ln in lines[i + 1:] if ln.strip()]
    return _cache[eid]


def build(eid, t1, t2):
    b = body(eid)
    i1 = [k for k, ln in enumerate(b) if ln.startswith(f"[{t1}]")]
    i2 = [k for k, ln in enumerate(b) if ln.startswith(f"[{t2}]")]
    if not i1 or not i2:
        sys.exit(f"{eid} {t1}~{t2} 时间戳不存在 (t1={bool(i1)}, t2={bool(i2)})")
    i, j = i1[0], i2[0]
    if j < i:
        sys.exit(f"{eid} {t1}~{t2} 起止顺序反了")
    chunk = b[i:j + 1]
    block = "> " + "\n> ".join(chunk) + f"\n\n—— `{eid}` `[{t1}]`~`[{t2}]`"
    return block, len(chunk)


tpl = TPL.read_text(encoding="utf-8")
labels = re.findall(r"\{\{([A-Za-z0-9]+)\}\}", tpl)
missing = [l for l in labels if l not in SPEC]
extra = [l for l in SPEC if l not in labels]
if missing:
    sys.exit(f"模板里有未定义的标签：{missing}")
if extra:
    sys.exit(f"SPEC 里有模板未用的标签：{extra}")
if len(labels) != len(set(labels)):
    dup = [l for l in set(labels) if labels.count(l) > 1]
    sys.exit(f"模板里重复的标签：{dup}")

for lab in labels:
    block, n = build(*SPEC[lab])
    tpl = tpl.replace("{{" + lab + "}}", block)
    print(f"{lab:4s} {SPEC[lab][0]:13s} {SPEC[lab][1]}~{SPEC[lab][2]}  {n:2d} 行")

if "{{" in tpl:
    sys.exit("还有未替换的占位符")

# 自检：每个「时间戳」字段必须与该节原话窗口一致（按文档出现顺序配对）
fields = re.findall(
    r"\| 时间戳 \| `(\[\d{2}:\d{2}:\d{2}\])`(?:~`(\[\d{2}:\d{2}:\d{2}\])`)?", tpl)
if len(fields) != len(labels):
    sys.exit(f"时间戳字段数 {len(fields)} != 引文块数 {len(labels)}")
for lab, (f1, f2) in zip(labels, fields):
    eid, t1, t2 = SPEC[lab]
    want1, want2 = f"[{t1}]", (f"[{t2}]" if f2 else "")
    if f1 != want1 or f2 != want2:
        sys.exit(f"{lab} 时间戳字段与引文窗口不符：表内 {f1}~{f2}，引文 {want1}~{want2}")
print("时间戳字段自检通过")

OUT.write_text(tpl, encoding="utf-8")
print(f"\n写出 {OUT}")
print(f"  {len(tpl)} 字符 / {len(labels)} 块引文")
