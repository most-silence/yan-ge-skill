# -*- coding: utf-8 -*-
"""逐行严格自验：批读产出里的每一行引文，必须与指定期次原文中该时间戳那行逐字一致。

verify_quotes.py 的盲区：
  1. 只抓「」型，且 split_frags 丢弃 <=6 字片段 —— 短句（「然后反拉」「牛就还在」）不验；
  2. 只比对「片段是否出现在全文」，不校验时间戳与该行是否对应 —— 串行/串期次验不出来。

本脚本补这两个洞：逐行、按时间戳、全字比对。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXT = ROOT / "sources" / "05-播客转写" / "audio_txt"
CAND = ROOT / "sources" / "05-播客转写" / "_规则候选"

TS = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$")


def load_source(eid):
    hits = list(TXT.glob(f"{eid}*._clean.txt"))
    if not hits:
        return None
    d = {}
    for ln in hits[0].read_text(encoding="utf-8", errors="ignore").splitlines():
        m = TS.match(ln.strip())
        if m:
            d.setdefault(m.group(1), []).append(m.group(2))
    return d


def main(path):
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()

    # 收集 stanza：连续 "> [ts] ..." 行 + 紧随的 "—— `eid` `[a]`~`[b]`"
    stanzas = []
    buf = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("> [") and re.match(r"^> \[\d{2}:\d{2}:\d{2}\]", s):
            buf.append(s[2:].strip())
        else:
            if buf:
                stanzas.append([buf, None])
                buf = []
            if s.startswith("—— `") and stanzas and stanzas[-1][1] is None:
                m = re.match(r"—— `([A-Za-z0-9]+)`", s)
                if m:
                    stanzas[-1][1] = m.group(1)
    if buf:
        stanzas.append([buf, None])

    src_cache = {}
    total = ok = 0
    fails = []
    for i, (rows, eid) in enumerate(stanzas, 1):
        if not eid:
            fails.append((i, "?", "缺期次行", rows[0]))
            total += len(rows)
            continue
        if eid not in src_cache:
            src_cache[eid] = load_source(eid)
        src = src_cache[eid]
        if src is None:
            fails.append((i, eid, "期次文件不存在", rows[0]))
            total += len(rows)
            continue
        for row in rows:
            total += 1
            m = TS.match(row)
            if not m:
                fails.append((i, eid, "行无时间戳", row))
                continue
            ts, body = m.group(1), m.group(2).strip()
            cands = src.get(ts, [])
            if not cands:
                fails.append((i, eid, f"原文无此时间戳 {ts}", body))
                continue
            # 该时间戳下必须有一行正文与引文完全一致（去首尾空白）
            if any(body == c.strip() for c in cands):
                ok += 1
            else:
                fails.append((i, eid, f"{ts} 正文不符", body))

    print(f"stanza 数: {len(stanzas)}  引文行: {total}  逐行命中: {ok}")
    print(f"逐行严格逐字率: {ok / total * 100 if total else 0:.1f}%")
    if fails:
        print(f"\n不合格 {len(fails)} 行：")
        for i, eid, why, body in fails:
            print(f"  #{i} {eid} [{why}] {body[:70]}")
        return 1
    print("PASS: 全部逐行、按期次、按时间戳逐字一致")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else CAND / "batch-61.md"))
