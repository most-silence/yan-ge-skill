#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch-18 定点返工：按小节编号重建引文块 + 同步表头时间戳。

背景：第一版 SPEC 里有几条窗口张冠李戴（C5/C6/C7/B9/A5/A6 互换或留了旧稿窗口），
导致脚本填进去的引文块与所在小节主题不符。这个脚本按小节锚点重贴，杜绝再错位。
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

# 小节编号 → (eid, start, end)   —— 全量重贴，避免残留错位
SPEC = {
    "A1": ("xXbq00mp4j8C", "00:09:48", "00:10:11"),
    "A2": ("xXbq00mp4j8C", "00:06:40", "00:06:54"),
    "A3": ("xXbq00mp4j8C", "00:13:12", "00:13:42"),
    "A4": ("xXbq00mp4j8C", "00:16:26", "00:16:37"),
    "A5": ("xXbq00mp4j8C", "00:11:32", "00:11:37"),
    "A6": ("xXbq00mp4j8C", "00:10:48", "00:11:26"),
    "A7": ("A8RQb9NRe5Zs", "00:01:20", "00:02:00"),
    "A8": ("A8RQb9NRe5Zs", "00:02:24", "00:02:37"),
    "A9": ("A8RQb9NRe5Zs", "00:09:11", "00:09:36"),
    "A10": ("A8RQb9NRe5Zs", "00:10:09", "00:10:24"),
    "A11": ("A8RQb9NRe5Zs", "00:15:17", "00:15:28"),
    "A12": ("A8RQb9NRe5Zs", "00:16:30", "00:16:43"),
    "A13": ("A8RQb9NRe5Zs", "00:04:25", "00:05:16"),
    "A14": ("9BJToFj5QFAr", "00:01:15", "00:01:45"),
    "A15": ("9BJToFj5QFAr", "00:08:05", "00:08:13"),
    "A16": ("9BJToFj5QFAr", "00:12:53", "00:13:43"),
    "A17": ("9BJToFj5QFAr", "00:16:15", "00:16:51"),
    "A18": ("9BJToFj5QFAr", "00:20:39", "00:20:54"),
    "A19": ("pEzd4aIgCMlt", "00:07:53", "00:08:17"),
    "A20": ("9BJToFj5QFAr", "00:21:16", "00:21:30"),
    "B1": ("xXbq00mp4j8C", "00:01:05", "00:01:09"),
    "B2": ("A8RQb9NRe5Zs", "00:02:59", "00:03:06"),
    "B3": ("A8RQb9NRe5Zs", "00:03:12", "00:03:31"),
    "B4": ("9BJToFj5QFAr", "00:07:43", "00:07:51"),
    "B5": ("pEzd4aIgCMlt", "00:11:24", "00:11:38"),
    "B6": ("9BJToFj5QFAr", "00:03:56", "00:04:35"),
    "B7": ("9BJToFj5QFAr", "00:04:51", "00:05:03"),
    "B8": ("A8RQb9NRe5Zs", "00:06:25", "00:06:39"),
    "B9": ("9BJToFj5QFAr", "00:19:30", "00:19:47"),
    "C1": ("A8RQb9NRe5Zs", "00:19:15", "00:19:26"),
    "C2": ("9BJToFj5QFAr", "00:06:45", "00:07:10"),
    "C3": ("xXbq00mp4j8C", "00:06:19", "00:06:27"),
    "C4": ("xXbq00mp4j8C", "00:15:53", "00:16:05"),
    "C5": ("pEzd4aIgCMlt", "00:06:27", "00:06:31"),
    "C6": ("A8RQb9NRe5Zs", "00:14:39", "00:14:59"),
    "C7": ("xXbq00mp4j8C", "00:10:32", "00:10:46"),
}

TS_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] ")
_lines_cache = {}


def load(eid):
    if eid not in _lines_cache:
        out = []
        p = TXT_DIR / EID_FILE[eid]
        for ln in p.read_text(encoding="utf-8").splitlines():
            m = TS_RE.match(ln)
            if m:
                out.append((m.group(1), ln))
        _lines_cache[eid] = out
    return _lines_cache[eid]


def make_block(eid, start, end):
    rows = [ln for ts, ln in load(eid) if start <= ts <= end]
    if not rows:
        raise SystemExit(f"!! 取不到行 {eid} {start}~{end}")
    body = "\n".join("> " + r for r in rows)
    return f"{body}\n\n—— `{eid}` `[{start}]`~`[{end}]`"


SECTION_RE = re.compile(r"^### ([ABC]\d+) · ", re.M)
QUOTE_BLOCK_RE = re.compile(
    r"(?:^> \[\d{2}:\d{2}:\d{2}\].*\n)+\n?—— `([A-Za-z0-9]+)` `\[\d{2}:\d{2}:\d{2}\]`~`\[\d{2}:\d{2}:\d{2}\]`",
    re.M,
)
HDR_RE = re.compile(r"\| 时间戳 \| `\[\d{2}:\d{2}:\d{2}\]`~`\[\d{2}:\d{2}:\d{2}\]` \|")
HDR1_RE = re.compile(r"\| 时间戳 \| `\[\d{2}:\d{2}:\d{2}\]` \|")


def main():
    text = OUT.read_text(encoding="utf-8")
    marks = [(m.group(1), m.start()) for m in SECTION_RE.finditer(text)]
    marks.append(("__END__", len(text)))

    pieces = [text[:marks[0][1]]]
    report = []
    for i in range(len(marks) - 1):
        sid, s = marks[i]
        e = marks[i + 1][1]
        sec = text[s:e]
        if sid not in SPEC:
            pieces.append(sec)
            continue
        eid, st, en = SPEC[sid]

        # 1) 换引文块（第一节：> [ts] 行 + 脚注）
        new_block = make_block(eid, st, en)
        sec2, n = QUOTE_BLOCK_RE.subn(lambda m: new_block, sec, count=1)
        if n != 1:
            raise SystemExit(f"!! {sid} 引文块替换失败 n={n}")

        # 2) 同步表头时间戳（含单行 `[ts]` 形态）
        hdr_new = f"| 时间戳 | `[{st}]`~`[{en}]` |"
        sec2, n1 = HDR_RE.subn(hdr_new, sec2, count=1)
        if n1 == 0:
            sec2, n2 = HDR1_RE.subn(f"| 时间戳 | `[{st}]` |", sec2, count=1)
        report.append(f"{sid:4s} {eid} {st}~{en}")
        pieces.append(sec2)

    text = "".join(pieces)
    OUT.write_text(text, encoding="utf-8")
    print("\n".join(report))
    print(f"\n共重贴 {len(report)} 个小节")


if __name__ == "__main__":
    main()
