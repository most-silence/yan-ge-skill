#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""merge_map_parts.py — 把 _map_part_<桶>__<片>.json 汇总成桶级 _merge_map_<桶>.json

分片 agent 各自写一片（每片 ≤6 条，写入不会中断），本脚本合并成桶级映射，
再由 apply_merge_map.py 一次性落盘。合并时按 cid 去重（同片重复保留）。

用法：python tools/merge_map_parts.py [桶名...]   # 缺省处理全部有分片的桶
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
RES = ROOT / "research"


def main():
    buckets = sys.argv[1:]
    parts = defaultdict(list)
    for p in sorted(RES.glob("_map_part_*.json")):
        name = p.stem.replace("_map_part_", "")
        bucket = name.rsplit("__", 1)[0]
        if buckets and bucket not in buckets:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ✗ {name}: 解析失败 {e}")
            continue
        items = d if isinstance(d, list) else (d.get("items") or d.get("entries") or [])
        parts[bucket].append((name, items))

    for bucket, chunk_list in parts.items():
        merged, seen = [], set()
        for name, items in chunk_list:
            for it in items:
                cid = it.get("cid")
                if cid in seen:
                    print(f"  ⚠️ {bucket}: {cid} 重复（{name}），跳过")
                    continue
                seen.add(cid)
                merged.append(it)
        out = RES / f"_merge_map_{bucket}.json"
        if out.exists():
            print(f"  ⚠️ {bucket}: 已有桶级映射，跳过（先删再跑）")
            continue
        out.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
        m = sum(1 for x in merged if x.get("mode") == "merge")
        s = sum(1 for x in merged if x.get("mode") == "single")
        print(f"  ✓ {bucket}: {len(merged)} 条（归入{m}/单列{s}）← {len(chunk_list)} 片")


if __name__ == "__main__":
    main()