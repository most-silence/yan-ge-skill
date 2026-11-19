#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""print_map_task.py — 打印某片的判定说明（给 agent 用的任务简报）"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

name = sys.argv[1]
t = json.loads((ROOT / "research" / "_map_tasks" / f"{name}.json").read_text(encoding="utf-8"))
print(f"桶: {t['bucket']}  片: {t['part']}")
print(f"增量文件: {t['increment_file']}")
print(f"节点清单: {t['node_list']}")
print(f"输出: {t['output']}")
print(f"待判 cid（{len(t['cids'])} 条）: {' '.join(t['cids'])}")
