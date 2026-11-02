#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时校验：对 batch-89 的每个引文块做「时间戳 + 文字」双重逐行比对。

verify_quotes.py 只比文字（去标点后子串），不校时间戳；本脚本补这一刀：
1. 每个 > [ts] 行必须与清洗稿里**同一位置**的原文行完全相同（按顺序连续匹配，
   不按时间戳建索引——原文允许同一秒出现多行）；
2. 整块在原文里必须是**连续的相邻行**（防止跨段拼接）；
3. 块尾声明的起止时间戳必须等于块首末行的时间戳。
"""
import re
import sys
from pathlib import Path

from _b89_dump import FILES

ROOT = Path(r"E:\AIProjetct\Nothing\眼哥")
CAND = ROOT / "sources" / "05-播客转写" / "_规则候选" / "batch-89.md"

STANZA = re.compile(
    r"((?:^> \[\d{2}:\d{2}:\d{2}\].*\n)+)\n—— `([A-Za-z0-9]+)` `\[(\d{2}:\d{2}:\d{2})\]`~`\[(\d{2}:\d{2}:\d{2})\]`",
    re.M,
)


def load(eid):
    rows = []
    for raw in FILES[eid].read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if len(s) > 11 and s[0] == "[" and s[3] == ":" and s[6] == ":" and s[9] == "]":
            rows.append(s)
    return rows


def find_run(src, block):
    """在 src 里找与 block 完全相同的连续行段，返回起始下标或 None"""
    n, m = len(src), len(block)
    for i in range(n - m + 1):
        if src[i:i + m] == block:
            return i
    return None


def main():
    text = CAND.read_text(encoding="utf-8")
    src = {e: load(e) for e in FILES}
    blocks = list(STANZA.finditer(text))
    bad, checked = [], 0

    for m in blocks:
        body, eid, t1, t2 = m.group(1), m.group(2), m.group(3), m.group(4)
        lines = [l.lstrip(">").strip() for l in body.strip().splitlines()]
        checked += len(lines)
        if eid not in src:
            bad.append(f"[期次不存在] {eid}")
            continue
        if find_run(src[eid], lines) is None:
            # 定位第一处对不上的行，给出产出 vs 原文
            head = lines[0]
            cand = [i for i, ln in enumerate(src[eid]) if ln == head]
            detail = ""
            if cand:
                i0 = cand[0]
                for k, ln in enumerate(lines):
                    if i0 + k >= len(src[eid]) or src[eid][i0 + k] != ln:
                        detail = (f"\n    第 {k+1} 行不符"
                                  f"\n      产出: {ln}"
                                  f"\n      原文: {src[eid][i0+k] if i0+k < len(src[eid]) else '(超出末尾)'}")
                        break
            else:
                detail = f"\n    块首行在原文中不存在: {head}"
            bad.append(f"[不在原文/不连续] {eid} {t1}~{t2}{detail}")
            continue
        if lines[0][1:9] != t1 or lines[-1][1:9] != t2:
            bad.append(f"[声明起止与首末行不符] {eid} 声明 {t1}~{t2} / 实际 "
                       f"{lines[0][1:9]}~{lines[-1][1:9]}")

    print(f"引文块: {len(blocks)}  逐行: {checked}")
    if bad:
        print(f"\n不合格 {len(bad)} 处：")
        for b in bad:
            print("  " + b)
        return 1
    print("逐行（时间戳+文字）与原文完全一致，每块在原文内连续，起止声明与首末行一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
