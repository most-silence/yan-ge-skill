#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时工具：按时间范围打印清洗稿原文行（供批读逐行抄录）。"""
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXT = ROOT / "sources" / "05-播客转写" / "audio_txt"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def main():
    eid, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
    files = list(TXT.glob(f"{eid}*_clean.txt"))
    if not files:
        print("not found")
        return 1
    lines = files[0].read_text(encoding="utf-8").splitlines()
    on = False
    for ln in lines:
        if not ln.startswith("["):
            continue
        ts = ln[1:9]
        if ts == start:
            on = True
        if on:
            print(ln)
        if on and ts == end:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
