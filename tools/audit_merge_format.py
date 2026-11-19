#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audit_merge_format.py — 复盘：第二轮增量产物是否与第一轮/存量格式一致

检查项（每桶）：
  1. 第二轮证据行格式：`- **增量（第二轮 2026-11-18）**：cid（`oid` `[ts]`）——…`
  2. 单列节点字段完整性：触发条件/动作/具体数字/跨阶段证据/代表原话/归入了/备注
  3. 单列节点是否有桶前缀（### B07-S004）
  4. 对账表是否有第二轮行
  5. 是否有「第二轮增量并入」标记
  6. 第二轮证据行数 vs 映射表 merge 数
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
MG = ROOT / "sources" / "05-播客转写" / "_归并"
RES = ROOT / "research"

EV_RE = re.compile(r"^- \*\*增量（第二轮 2026-11-18）\*\*：(B\d{2}-\d{3})（`([A-Za-z0-9]+)` `\[(\d{2}:\d{2}:\d{2})\]`）", re.M)
NODE_RE = re.compile(r"^(#{3,4})\s+(?:([A-Z]\d{2})-)?(S\d+)\s*·", re.M)
REQUIRED = ["触发条件", "动作", "具体数字", "跨阶段证据", "代表原话", "归入了", "备注"]


def main():
    buckets = sorted(f.stem for f in MG.glob("*.md"))
    print(f"{'桶':<16} {'二轮行':>6} {'映射':>4} {'单列':>4} {'字段缺':>6} {'无前缀':>6} {'对账':>5} {'标记':>4}")
    problems = []
    for b in buckets:
        t = (MG / f"{b}.md").read_text(encoding="utf-8")
        if "第二轮增量" not in t:
            print(f"{b.split('-')[0]:<16} {'—':>6} {'—':>4} {'—':>4} {'—':>6} {'—':>6} {'—':>5} {'未做':>4}")
            continue
        ev = EV_RE.findall(t)
        mp = RES / f"_merge_map_{b}.json"
        n_merge = 0
        if mp.exists():
            d = json.loads(mp.read_text(encoding="utf-8"))
            items = d if isinstance(d, list) else (d.get("items") or [])
            n_merge = sum(1 for x in items if x.get("mode") == "merge")

        # 第二轮单列节点：S 号 > 第一轮最大号（粗判：找备注含 batch-99/100/101 的 S 节点）
        seg_start = t.find("第二轮增量并入")
        seg = t[max(0, seg_start - 20000):seg_start] if seg_start > 0 else t
        singles = re.findall(r"^#{3,4}\s+([A-Z]\d{2}-)?(S\d+)\s*·[^\n]*\n(.*?)(?=^#{3,4}|\Z)",
                             seg, re.M | re.S)
        bad_fields, no_prefix = 0, 0
        for pre, sid, body in singles:
            # 只查第二轮新增的单列节点：第一轮节点用「- 内容：」体例，字段结构不同
            if "batch-99/100/101" not in body:
                continue
            miss = [f for f in REQUIRED if f"**{f}**" not in body]
            if miss:
                bad_fields += 1
                problems.append(f"{b} {sid}: 缺字段 {miss}")
            if not pre:
                no_prefix += 1
                problems.append(f"{b} {sid}: 单列无桶前缀")
        n_single_r2 = sum(1 for pre, sid, body in singles if "batch-99/100/101" in body)
        recon = len(re.findall(r"^\|[^|\n]*B\d{2}-\d{3}[^|\n]*\|[^|\n]*→", t, re.M))
        mark = "✓" if "第二轮增量并入" in t else "✗"
        flag = "" if (len(ev) == n_merge and bad_fields == 0 and no_prefix == 0 and mark == "✓") else " ⚠️"
        print(f"{b.split('-')[0]:<16} {len(ev):>6} {n_merge:>4} {n_single_r2:>4} "
              f"{bad_fields:>6} {no_prefix:>6} {'有' if recon else '无':>5} {mark:>4}{flag}")
    print()
    if problems:
        print(f"问题 {len(problems)} 项：")
        for p in problems[:25]:
            print(" ", p)
    else:
        print("格式问题：无")


if __name__ == "__main__":
    main()
