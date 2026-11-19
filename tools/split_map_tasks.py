#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""split_map_tasks.py — 把待归并的桶按「每片 ≤6 条候选」切成任务片

为什么切片：agent 构造 20–28 条的 JSON 时长且易中断，中断=全丢。
切成 5–6 条的小片后，单片写入几乎不可能失败；多派几轮而已。

输出：research/_map_tasks/<桶名>__<片号>.json（每片含待判定的 cid 列表）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
INC = ROOT / "sources" / "05-播客转写" / "_增量条目"
OUT = ROOT / "research" / "_map_tasks"
OUT.mkdir(parents=True, exist_ok=True)

# 已完成映射的桶（跳过）
done = set()
for p in (ROOT / "research").glob("_merge_map_*.json"):
    done.add(p.stem.replace("_merge_map_", ""))

MAX = 6
tasks = []
for f in sorted(INC.glob("*.md")):
    bucket = f.stem
    if bucket in done:
        continue
    t = f.read_text(encoding="utf-8")
    cids = re.findall(r"^## (B\d{2}-\d{3})", t, re.M)
    if not cids:
        continue
    for i in range(0, len(cids), MAX):
        chunk = cids[i:i + MAX]
        idx = i // MAX + 1
        name = f"{bucket}__{idx}"
        (OUT / f"{name}.json").write_text(json.dumps(
            {"bucket": bucket, "part": idx, "cids": chunk,
             "increment_file": f"sources/05-播客转写/_增量条目/{bucket}.md",
             "node_list": f"research/_节点清单_{bucket}.txt",
             "output": f"research/_map_part_{name}.json"},
            ensure_ascii=False, indent=1), encoding="utf-8")
        tasks.append({"task": name, "bucket": bucket, "n": len(chunk)})

for t in tasks:
    print(f"  {t['task']}: {t['n']} 条")
print(f"\n共 {len(tasks)} 片（{len(set(t['bucket'] for t in tasks))} 个桶）")
(ROOT / "research" / "_map_tasks_index.json").write_text(
    json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
