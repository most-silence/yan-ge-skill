#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时工具：按 eid + 时间戳区间打印清洗稿原文行（供 batch-62 批读核对）"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXT = ROOT / "sources" / "05-播客转写" / "audio_txt"

EID_FILES = {
    "wcm72p8939F9": "wcm72p8939F9_眼哥股市会 10月24日._clean.txt",
    "bGDgBMp28uAx": "bGDgBMp28uAx_眼哥股市会 2月26日._clean.txt",
    "NlMwypMihiFF": "NlMwypMihiFF_眼哥股市会 6月22日._clean.txt",
    "6ad6e3f4b83cbb2aa3ef7b5a": "6ad6e3f4b83cbb2aa3ef7b5a_眼哥股市会 26.10.20._clean.txt",
}


def load(eid):
    txt = (TXT / EID_FILES[eid]).read_text(encoding="utf-8")
    lines = []
    for raw in txt.splitlines():
        s = raw.strip()
        if s.startswith("[") and "]" in s:
            ts = s[1:s.index("]")]
            body = s[s.index("]") + 1:].strip()
            lines.append((ts, body))
    return lines


if __name__ == "__main__":
    eid = sys.argv[1]
    a = sys.argv[2] if len(sys.argv) > 2 else "00:00:00"
    b = sys.argv[3] if len(sys.argv) > 3 else "99:99:99"
    out = []
    lines = load(eid)
    out.append(f"# {eid} 共 {len(lines)} 行")
    for i, (ts, body) in enumerate(lines):
        if a <= ts <= b:
            out.append(f"{i:4d} [{ts}] {body}")
    path = ROOT / "tools" / "_b62_dump.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {len(out)} lines -> {path}")
