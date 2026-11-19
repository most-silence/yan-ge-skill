#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_applied.py — 核查已 apply 的桶：每条第二轮证据行落在哪个节点块下

用法：python tools/verify_applied.py <桶名> [<桶名>...]
默认核查全部有第二轮标记的桶。报告：
  - 错位的证据行（所在块 ≠ 映射 target）
  - single 节点命名是否与存量一致（带不带桶前缀）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
MERGE = ROOT / "sources" / "05-播客转写" / "_归并"

HDR = re.compile(r"^(#{3,4})\s+(?:([A-Z]\d{2})-)?([A-Z]\d+(?:-[A-Z])?)\s*·", re.M)


def main():
    buckets = sys.argv[1:]
    if not buckets:
        buckets = [f.stem for f in sorted(MERGE.glob("*.md"))
                   if "第二轮增量" in f.read_text(encoding="utf-8")]

    total_bad = 0
    for bucket in buckets:
        f = MERGE / f"{bucket}.md"
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8")
        if "第二轮增量" not in t:
            continue
        mp = ROOT / "research" / f"_merge_map_{bucket}.json"
        if not mp.exists():
            print(f"{bucket}: 缺映射文件，跳过核查")
            continue
        d = json.loads(mp.read_text(encoding="utf-8"))
        items = d if isinstance(d, list) else (d.get("items") or d.get("entries") or [])
        want = {x["cid"]: x["target"] for x in items if x.get("mode") == "merge"}

        # 切块并记录每块的「桶前缀 + 节点号」
        parts = re.split(r"(?=^#{3,4}\s)", t, flags=re.M)
        bad = []
        single_naming = []
        for blk in parts:
            m = HDR.match(blk)
            if not m:
                # 无标题块：可能吞了证据行
                for cid in re.findall(r"：(B\d{2}-\d{3})（", blk):
                    if cid in want:
                        bad.append((cid, want[cid], "(无标题块)"))
                continue
            prefix, nid = m.group(2) or "", m.group(3)
            if re.match(r"^[A-Z]\d{3}$", nid) and not prefix:
                single_naming.append(nid)
            for cid in re.findall(r"：(B\d{2}-\d{3})（", blk):
                if cid in want and want[cid] != nid:
                    bad.append((cid, want[cid], f"{prefix}-{nid}" if prefix else nid))
        total_bad += len(bad)
        flag = "✅" if not bad else "❌"
        extra = f"  ⚠️单列命名无前缀 {len(single_naming)} 个" if single_naming else ""
        print(f"{flag} {bucket}: 错位 {len(bad)}{extra}")
        for cid, tgt, loc in bad[:6]:
            print(f"     {cid} 应在 {tgt}，实际在 {loc}")

    print(f"\n合计错位 {total_bad} 条")
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
