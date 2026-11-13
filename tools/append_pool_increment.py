#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""append_pool_increment.py — 把增量批（96/97/98）的候选卡并入规则池

池内编号接续：现有 2,611 条（P0001..P2611）→ 新条从 P2612 起。
只追加不改序——这是「已完成归并产出继续有效」的前提
（bucket_rules.py 重跑时旧候选的桶内编号不变）。

新卡字段从卡片表提取：编号/规则名/期次 eid/时间戳/触发/动作/数字/原话/阶段。
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

POOL = ROOT / "sources" / "05-播客转写" / "_规则池.json"
BATCHES = ["batch-96", "batch-97", "batch-98"]
FIELD_LABELS = ["触发", "动作", "数字", "原话", "边界声明", "跨阶段", "备注", "冲突"]

# 96/97 带段落前缀：### A1 · B96-001 · 名字；98 直接：## B98-001 · 名字
CAND_HDR = re.compile(r"^#{2,4}\s+(?:[A-E]\d+\s*·\s*)?(B9[678]-\d{3})\s*·\s*(.+)$", re.M)

# 字段名变体：96/97 用「触发条件/动作」，98 用「触发/动作」
FIELD_VARIANTS = {
    "trigger": ["触发条件", "触发"],
    "action": ["动作", "具体动作"],
    "numbers": ["具体数字", "数字"],
}


def extract_field(body, label):
    m = re.search(r"\*\*" + label + r"\*\*[：:]?", body)
    if not m:
        return ""
    start = m.end()
    tail = body[start:]
    end = len(tail)
    for other in FIELD_LABELS:
        if other == label:
            continue
        om = re.search(r"\*\*" + other + r"\*\*", tail)
        if om:
            end = min(end, om.start())
    return re.sub(r"\s+", " ", tail[:end]).strip().lstrip("-：:").strip()


def parse_batch(path, regime="R8"):
    text = path.read_text(encoding="utf-8")
    marks = [(m.start(), m.group(1), m.group(2).strip()) for m in CAND_HDR.finditer(text)]
    out = []
    for i, (pos, cid, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = text[pos:end]
        eid = re.search(r"期次[^`\n]*`([A-Za-z0-9]+)`", body)
        ts = re.search(r"\[(\d{2}:\d{2}:\d{2})\]", body)
        quote = re.search(r"((?:^> \[\d{2}:\d{2}:\d{2}\][^\n]*\n)+)[^\n]*—— `([A-Za-z0-9]+)`",
                          body, re.M)
        quote_lines = quote.group(1).rstrip("\n") if quote else ""
        out.append({
            "cid": cid,
            "batch": path.stem,
            "name": name,
            "eid": eid.group(1) if eid else "",
            "ts": ts.group(1) if ts else "",
            "regime": regime,
            "trigger": extract_field(body, "触发条件") or extract_field(body, "触发"),
            "action": extract_field(body, "动作"),
            "numbers": extract_field(body, "具体数字") or extract_field(body, "数字"),
            "quote": quote_lines,
        })
    return out


def main():
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    n_old = len(pool["rules"])
    print(f"现有池：{n_old} 条")

    new_rules = []
    for b in BATCHES:
        f = ROOT / "sources" / "05-播客转写" / "_规则候选" / f"{b}.md"
        cards = parse_batch(f)
        print(f"  {b}: {len(cards)} 张卡")
        for c in cards:
            new_rules.append({
                "key": c["cid"],
                "name": c["name"],
                "count": 1,
                "regimes": [c["regime"]],
                "n_regimes": 1,
                "eids": [c["eid"]],
                "batches": [c["batch"]],
                "strength": "增量",
                "evidence": [{
                    "batch": c["batch"], "eid": c["eid"], "date": "",
                    "regime": c["regime"], "ts": c["ts"],
                    "quote": c["quote"],
                    "trigger": c["trigger"], "action": c["action"],
                    "numbers": c["numbers"],
                }],
            })

    # 去重保护：同 key 已存在就跳过（幂等）
    existing_keys = {r["key"] for r in pool["rules"]}
    added = [r for r in new_rules if r["key"] not in existing_keys]
    pool["rules"].extend(added)

    POOL.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n追加 {len(added)} 条（跳过重复 {len(new_rules)-len(added)}）")
    print(f"池现规模：{len(pool['rules'])} 条（P2612 起为新条）")


if __name__ == "__main__":
    main()
