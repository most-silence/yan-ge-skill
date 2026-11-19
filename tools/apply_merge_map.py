#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""apply_merge_map.py — 把归入映射表确定性地写入归并文件（简单可靠版）

分工：agent 只产出映射 JSON（判断，小写入不会留半成品），
本脚本做机械编辑（追加证据行 + 对账行 + 标记）。脚本不会中途死。

用法：python tools/apply_merge_map.py <桶名>
映射：research/_merge_map_<桶名>.json =
  [{"cid","mode":"merge|single","target":"Mxx"|"Sxx"|"单列",
    "oid","ts","brief", "single_name"(single 时), "single_body"(single 时)}]

幂等：证据行/对账行已存在则跳过该 cid。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
MERGE = ROOT / "sources" / "05-播客转写" / "_归并"


def main():
    if len(sys.argv) < 2:
        print("用法: apply_merge_map.py <桶名>"); return 1
    bucket = sys.argv[1]
    mp = ROOT / "research" / f"_merge_map_{bucket}.json"
    if not mp.exists():
        print(f"缺映射 {mp.name}"); return 1
    raw = json.loads(mp.read_text(encoding="utf-8"))
    # 兼容两种格式：裸数组，或 {"items"/"entries"/"map":[...]}
    entries = raw if isinstance(raw, list) else (
        raw.get("items") or raw.get("entries") or raw.get("map") or [])

    # 从增量条目文件按 cid 回查真实 oid/ts（agent 常填错）
    # 块切分：每个 ## Bxx-NNN 块内，期次字段取 24 位 oid，证据行取首个 [ts]
    inc_file = ROOT / "sources" / "05-播客转写" / "_增量条目" / f"{bucket}.md"
    oid_ts = {}
    if inc_file.exists():
        bt = chr(96)  # 反引号，避免源码里字面反引号被工具链转义
        blocks = re.split(r"(?=^## B\d{2}-\d{3})", inc_file.read_text(encoding="utf-8"), flags=re.M)
        for b in blocks:
            m = re.match(r"## (B\d{2}-\d{3})", b)
            if not m:
                continue
            oid = re.search(r"期次\s*\|\s*" + bt + r"([A-Za-z0-9]{12,24})" + bt, b)
            ts = re.search(bt + r"\[(\d{2}:\d{2}:\d{2})\]" + bt, b)
            oid_ts[m.group(1)] = (oid.group(1) if oid else "", ts.group(1) if ts else "")

    for e in entries:
        cid = e["cid"]
        real_oid, real_ts = oid_ts.get(cid, ("", ""))
        if not re.fullmatch(r"[A-Za-z0-9]{24}", str(e.get("oid", ""))):
            e["oid"] = real_oid or e.get("oid", "")
        ts = re.sub(r"[\[\]]", "", str(e.get("ts", "")))
        if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", ts):
            ts = real_ts
        e["ts"] = ts

    f = MERGE / f"{bucket}.md"
    t = f.read_text(encoding="utf-8")

    # 节点标题格式：### M01 · / ### B07-M45 · / #### A01 ·（B18 四级）
    NODE_RE = r"^(#{3,4})\s+(?:[A-Z]\d{2}-)?([A-Z]\d+(?:-[A-Z])?)\s*·"

    # 按任意标题切块（#{2,4} 都切）——二级标题「## 三、冲突清单」也必须切，
    # 否则最后一个节点块会把冲突清单+对账表全吞进去，证据行被追加到文件末尾
    # （表现为 verify 报「错位：应在 S003，实际在 S004」）。
    parts = re.split(r"(?=^#{2,4}\s)", t, flags=re.M)

    def block_id(blk):
        m = re.match(r"^#{3,4}\s+(?:[A-Z]\d{2}-)?([A-Z]\d+(?:-[A-Z])?)\s*·", blk)
        return m.group(1) if m else None

    # 证据行按 target 分组
    ev_by_target = {}
    for e in entries:
        if e["mode"] != "merge":
            continue
        ev_by_target.setdefault(e["target"], []).append(
            f"- **增量（第二轮 2026-11-18）**：{e['cid']}（`{e['oid']}` "
            f"`[{e['ts']}]`）——{e['brief']}")

    n_ev = n_skip = 0
    for i, blk in enumerate(parts):
        bid = block_id(blk)
        if bid and bid in ev_by_target:
            # 幂等：该 target 的第一条证据行已存在就整组跳过
            first = ev_by_target[bid][0]
            if first in blk or re.search(r"增量（第二轮[^\n]*" + re.escape(bid), blk):
                # 逐条判重
                add = [ln for ln in ev_by_target[bid] if ln not in blk]
            else:
                add = ev_by_target[bid]
            if add:
                parts[i] = blk.rstrip() + "\n" + "\n".join(add) + "\n\n"
                n_ev += len(add)
            else:
                n_skip += len(ev_by_target[bid])
            del ev_by_target[bid]
    # 没匹配到任何块的 target（节点编号写错）
    for tgt, lines in ev_by_target.items():
        print(f"  ⚠️ target {tgt} 无对应节点块，{len(lines)} 条未落")
        n_skip += len(lines)
    t = "".join(parts)

    n_rec = 0
    bprefix = bucket.split("-")[0]  # B07 / B12 / X
    for e in entries:
        if e["mode"] == "merge":
            continue  # 已处理
        # single：整段追加到「三、冲突清单」前
        sid = e.get("single_id", e["cid"])
        full_id = f"{bprefix}-{sid}" if not sid.startswith(bprefix) else sid
        if re.search(r"#{3,4}\s+" + re.escape(full_id) + r"\b", t):
            n_skip += 1; continue
        body = e.get("single_body", "")
        # 把「触发：…动作：…具体数字：…」散文化成分行（对齐存量节点格式）
        def fmt_line(label, text):
            return f"- **{label}**：{text.strip()}"
        parts_b = []
        seg_pat = re.compile(r"(触发|触发条件|动作|具体数字|原话|落点|备注)[：:]")
        marks = [(m.group(1), m.start(), m.end()) for m in seg_pat.finditer(body)]
        if marks:
            for k, (lab, s0, e0) in enumerate(marks):
                s1 = marks[k + 1][1] if k + 1 < len(marks) else len(body)
                txt = body[e0:s1].strip().rstrip("。.")
                lab_full = {"触发": "触发条件", "触发条件": "触发条件"}.get(lab, lab)
                parts_b.append(fmt_line(lab_full, txt))
            node = (f"\n### {full_id} · {e.get('single_name','')}\n\n"
                    + "\n".join(parts_b) + "\n")
        else:
            node = (f"\n### {full_id} · {e.get('single_name','')}\n\n"
                    + body + "\n")
        ins = re.search(r"\n## 三、冲突清单", t)
        t = (t[:ins.start()] + node + t[ins.start():]) if ins else t.rstrip() + "\n" + node

    # 对账表：四栏追加
    rows = []
    for e in entries:
        tgt = e["target"] if e["mode"] == "merge" else f"单列 {e.get('single_id','')}"
        rows.append(f"{e['cid']} | → {tgt}")
    rec = []
    for i in range(0, len(rows), 4):
        ch = rows[i:i + 4]
        ch += [" | "] * (4 - len(ch))
        rec.append("| " + " | ".join(ch) + " |")
    if rec:
        t = t.rstrip() + "\n" + "\n".join(rec) + "\n"
        n_rec = len(rows)

    # 标记
    n_m = sum(1 for e in entries if e["mode"] == "merge")
    n_s = sum(1 for e in entries if e["mode"] == "single")
    if "第二轮增量并入" not in t:
        foot = f"\n> 第二轮增量并入：{n_m} 归入 / {n_s} 单列（batch-99/100/101，2026-11-18）\n\n"
        ins = re.search(r"\n## 三、冲突清单", t)
        t = (t[:ins.start()] + foot + t[ins.start():]) if ins else t.rstrip() + "\n\n" + foot

    f.write_text(t, encoding="utf-8")
    print(f"{bucket}: 证据行+{n_ev} 单列+{n_s} 对账+{n_rec} 跳过{n_skip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
