#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""batch-18 修补：把若干条引文块按新时间窗重新从原文导出，并同步表头时间戳。

用法：改 PATCH 里的 (old_footer_ts_start, new_start, new_end)，跑一次。
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

# (eid, 旧起, 旧止, 新起, 新止, 表头里旧的时间戳行)
PATCH = [
    ("xXbq00mp4j8C", "00:06:40", "00:06:54", "00:06:40", "00:07:03"),
    ("A8RQb9NRe5Zs", "00:05:00", "00:05:16", "00:04:47", "00:05:16"),
]

TS_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] ")


def load(eid):
    p = TXT_DIR / EID_FILE[eid]
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        m = TS_RE.match(ln)
        if m:
            out.append((m.group(1), ln))
    return out


def make_block(eid, start, end):
    rows = [ln for ts, ln in load(eid) if start <= ts <= end]
    if not rows:
        raise SystemExit(f"!! 取不到行 {eid} {start}~{end}")
    body = "\n".join("> " + r for r in rows)
    return f"{body}\n\n—— `{eid}` `[{start}]`~`[{end}]`"


def main():
    text = OUT.read_text(encoding="utf-8")
    for eid, os_, oe, ns, ne in PATCH:
        old_foot = f"—— `{eid}` `[{os_}]`~`[{oe}]`"
        if old_foot not in text:
            raise SystemExit(f"!! 找不到旧脚注 {old_foot}")
        # 该脚注前面连续的 "> [ts]" 行整体替换
        pat = re.compile(
            r"(?:^> \[\d{2}:\d{2}:\d{2}\].*\n)+" + re.escape(old_foot),
            re.M,
        )
        new = make_block(eid, ns, ne)
        text, n = pat.subn(new.replace("\\", "\\\\"), text, count=1)
        if n != 1:
            raise SystemExit(f"!! {eid} 替换失败 n={n}")
        # 表头时间戳
        if (os_, oe) != (ns, ne):
            old_hdr = f"`[{os_}]`~`[{oe}]`"
            new_hdr = f"`[{ns}]`~`[{ne}]`"
            if old_hdr not in text:
                raise SystemExit(f"!! 找不到表头 {old_hdr}")
            text = text.replace(old_hdr, new_hdr)
        print(f"  已修补 {eid} {ns}~{ne}")
    OUT.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
