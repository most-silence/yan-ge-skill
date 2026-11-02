#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch-18 专用：把 md 里的 @@占位符@@ 换成按时间戳从清洗稿导出的逐行引文块。

为什么用脚本生成引文：v1 的教训是「人会不自觉把碎片读顺」。
这里直接把原文行搬过来，零改写空间。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = ROOT / "sources" / "05-播客转写" / "audio_txt"
OUT = ROOT / "sources" / "05-播客转写" / "_规则候选" / "batch-18.md"

EID_FILE = {
    "xXbq00mp4j8C": "xXbq00mp4j8C_眼哥股市会 5月18日._clean.txt",
    "A8RQb9NRe5Zs": "A8RQb9NRe5Zs_眼哥股市会 8月12日._clean.txt",
    "9BJToFj5QFAr": "9BJToFj5QFAr_眼哥股市会 9月10日._clean.txt",
    "pEzd4aIgCMlt": "pEzd4aIgCMlt_说在8月开盘前._clean.txt",
}

# key → (eid, start_ts, end_ts)
SPEC = {
    "A1": ("xXbq00mp4j8C", "00:09:48", "00:10:11"),
    "A2": ("xXbq00mp4j8C", "00:06:40", "00:06:54"),
    "A3": ("xXbq00mp4j8C", "00:13:12", "00:13:22"),
    "A4": ("xXbq00mp4j8C", "00:16:26", "00:16:37"),
    "A5": ("xXbq00mp4j8C", "00:11:09", "00:11:26"),
    "A6": ("xXbq00mp4j8C", "00:11:32", "00:11:37"),
    "A7": ("A8RQb9NRe5Zs", "00:01:20", "00:01:39"),
    "A8": ("A8RQb9NRe5Zs", "00:02:24", "00:02:37"),
    "A9": ("A8RQb9NRe5Zs", "00:09:11", "00:09:36"),
    "A10": ("A8RQb9NRe5Zs", "00:10:09", "00:10:24"),
    "A11": ("A8RQb9NRe5Zs", "00:15:17", "00:15:28"),
    "A12": ("A8RQb9NRe5Zs", "00:16:30", "00:16:43"),
    "A13": ("A8RQb9NRe5Zs", "00:05:00", "00:05:16"),
    "A14": ("9BJToFj5QFAr", "00:01:15", "00:01:45"),
    "A15": ("9BJToFj5QFAr", "00:08:05", "00:08:09"),
    "A16": ("9BJToFj5QFAr", "00:13:13", "00:13:43"),
    "A17": ("9BJToFj5QFAr", "00:16:15", "00:16:31"),
    "A18": ("9BJToFj5QFAr", "00:20:39", "00:20:54"),
    "A19": ("pEzd4aIgCMlt", "00:08:07", "00:08:17"),
    "A20": ("9BJToFj5QFAr", "00:21:16", "00:21:30"),
    "B1": ("xXbq00mp4j8C", "00:01:05", "00:01:09"),
    "B2": ("A8RQb9NRe5Zs", "00:02:59", "00:03:06"),
    "B3": ("A8RQb9NRe5Zs", "00:03:12", "00:03:21"),
    "B4": ("9BJToFj5QFAr", "00:07:47", "00:07:47"),
    "B5": ("pEzd4aIgCMlt", "00:11:24", "00:11:38"),
    "B6": ("9BJToFj5QFAr", "00:03:56", "00:04:18"),
    "B7": ("9BJToFj5QFAr", "00:04:51", "00:05:03"),
    "B8": ("A8RQb9NRe5Zs", "00:06:25", "00:06:39"),
    "B9": ("9BJToFj5QFAr", "00:21:16", "00:21:30"),
    "C1": ("A8RQb9NRe5Zs", "00:19:15", "00:19:26"),
    "C2": ("9BJToFj5QFAr", "00:06:45", "00:07:10"),
    "C3": ("xXbq00mp4j8C", "00:15:23", "00:15:35"),
    "C4": ("xXbq00mp4j8C", "00:15:53", "00:16:05"),
    "C5": ("A8RQb9NRe5Zs", "00:14:59", "00:15:07"),
    "C6": ("pEzd4aIgCMlt", "00:06:27", "00:06:44"),
    "C7": ("xXbq00mp4j8C", "00:05:40", "00:05:45"),
}

TS_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] ")


def load(eid):
    p = TXT_DIR / EID_FILE[eid]
    lines = p.read_text(encoding="utf-8").splitlines()
    out = []
    for ln in lines:
        m = TS_RE.match(ln)
        if m:
            out.append((m.group(1), ln))
    return out


def block(key):
    eid, start, end = SPEC[key]
    rows = [ln for ts, ln in load(eid) if start <= ts <= end]
    if not rows:
        raise SystemExit(f"!! {key} 取不到行 {eid} {start}~{end}")
    body = "\n".join("> " + r for r in rows)
    return f"{body}\n\n—— `{eid}` `[{start}]`~`[{end}]`"


def main():
    text = OUT.read_text(encoding="utf-8")
    for key in SPEC:
        ph = f"@@{key}@@"
        if ph not in text:
            print(f"  跳过（md 里没有 {ph}）")
            continue
        text = text.replace(ph, block(key))
    left = re.findall(r"@@[A-Z]\d+@@", text)
    if left:
        raise SystemExit(f"!! 还有未替换占位符: {left}")
    OUT.write_text(text, encoding="utf-8")
    print(f"已填充 {len(SPEC)} 个引文块 → {OUT.name}")


if __name__ == "__main__":
    main()
