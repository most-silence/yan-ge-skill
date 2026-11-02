#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 batch-60 批读产出：引文块按时间戳区间从 *_clean.txt 原样抽取。

不手抄引文。分析文字手写，引文一律程序取行，避免「读顺」。
"""
import re
import sys
from pathlib import Path

ROOT = Path(r"E:\AIProjetct\Nothing\眼哥")
TXT = ROOT / "sources" / "05-播客转写" / "audio_txt"
OUT = ROOT / "sources" / "05-播客转写" / "_规则候选" / "batch-60.md"

FILES = {
    "RTl1r6Dm5BdB": "RTl1r6Dm5BdB_一点加更 几句废话._clean.txt",
    "KKJKoAOUeZAB": "KKJKoAOUeZAB_眼哥股市会 8.11日._clean.txt",
    "slAPXx8GT3TB": "slAPXx8GT3TB_眼哥股市会 10月23日._clean.txt",
    "KeTnhYpS5y8l": "KeTnhYpS5y8l_眼哥股市会 2月25日._clean.txt",
}

TS = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s?")


def load(eid):
    p = TXT / FILES[eid]
    raw = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows = []
    for ln in raw:
        m = TS.match(ln)
        if m:
            rows.append((m.group(1), ln.rstrip()))
    return rows


CACHE = {}


def rows_of(eid):
    if eid not in CACHE:
        CACHE[eid] = load(eid)
    return CACHE[eid]


def block(eid, t1, t2):
    rows = rows_of(eid)
    i = next((k for k, (ts, _) in enumerate(rows) if ts >= t1), None)
    if i is None:
        raise SystemExit(f"{eid}: 起点 {t1} 超出范围")
    if rows[i][0] != t1:
        print(f"! {eid} 起点 {t1} 不存在，退到 {rows[i][0]}", file=sys.stderr)
    j = max(k for k, (ts, _) in enumerate(rows) if ts <= t2)
    if rows[j][0] != t2:
        print(f"! {eid} 终点 {t2} 不存在，退到 {rows[j][0]}", file=sys.stderr)
    if j < i:
        raise SystemExit(f"{eid}: 区间 {t1}~{t2} 为空")
    return "\n".join("> " + ln for _, ln in rows[i:j + 1])


MARK = re.compile(r"^@@([A-Za-z0-9]+)\|(\d{2}:\d{2}:\d{2})\|(\d{2}:\d{2}:\d{2})@@$", re.M)


def main():
    tpl = (ROOT / "tools" / "_b60_tpl.md").read_text(encoding="utf-8")

    def rep(m):
        return block(m.group(1), m.group(2), m.group(3))

    md = MARK.sub(rep, tpl)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(md, encoding="utf-8")
    print(f"写出 {OUT}")
    print(f"引文块 {len(MARK.findall(tpl))} 个")


if __name__ == "__main__":
    main()
