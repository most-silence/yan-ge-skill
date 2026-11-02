#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""candidate_trace.py — 候选级跨桶追踪（精确，非启发式）

为什么不用文本相似度
--------------------
先试过用「触发+动作」的正文相似度找跨桶重复，只找到 37 对。
但那不可靠——同一条规则被不同桶从不同角度描述时，文字会差很远：

    止损桶：破位即止损，技术位失守就走，割错也走
    减仓桶：破位就减仓/清仓，越过技术位即处置

这两条其实是同一件事的两面（一个是「走不走」，一个是「走多少」），
但文字相似度只有 0.3 左右，会被漏掉。

正确做法：追候选编号
--------------------
每个候选都有唯一编号（B01-001、B18-332）。它在落进桶时就已经被记下：
桶文件里 `## B01-001 · 规则名` 是候选，归并产出的对账表写它 `→ M05`。

所以「候选 X 同时出现在 B01/M05 和 B06/M02 里」是**精确事实**，
不需要猜。这才是跨桶关系的可靠来源。

能得出什么
----------
1. 每个候选落进了哪些桶、各自归到哪条规则
2. 哪些规则通过共享候选而关联（跨桶规则图）
3. 哪些候选是「跨主题综合规则」——落进桶多、且被归到不同规则
4. 真正只在单个桶里出现的规则（无需跨桶合并）

输出
----
  _候选追踪.json
  _候选追踪.md
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUCKET_DIR = ROOT / "sources" / "05-播客转写" / "_分桶"
MERGE_DIR = ROOT / "sources" / "05-播客转写" / "_归并"
OUT_JSON = ROOT / "sources" / "05-播客转写" / "_候选追踪.json"
OUT_MD = ROOT / "sources" / "05-播客转写" / "_候选追踪.md"

# 两个桶的规则要共享多少条候选，才算「同一规则的不同侧面」
SHARE_STRONG = 3   # ≥3 条共享 → 强关联，几乎肯定是同一条规则
SHARE_WEAK = 2     # 2 条 → 待人工确认

# 桶文件里的候选块：## B01-001 · 规则名   或   ## X001 · 规则名
CAND_HDR = re.compile(r"^##\s+([A-Z]\d{2}-\d{3}|[A-Z]\d{3,4})\s*[·.]\s*(.+)$", re.M)


def norm_cid(bucket, cid):
    """统一候选编号：X 桶用 X001，其余用 BNN-001"""
    if re.fullmatch(r"[A-Z]\d{3,4}", cid):
        return cid
    return cid


def parse_candidates(path):
    """桶文件：桶内编号 → (规则名, 池内编号, 期次, 阶段)

    ⚠️ 关键教训：桶内编号（B01-001）是**局部**的——每个桶都从 001 重来，
    所以 B01-001 和 B06-001 是完全不同的候选，用它追不了跨桶关系。
    第一版就栽在这里：9,762 条候选全部显示「跨 1 个桶」。

    池内编号 P0002 是**全局唯一**的，这才认得出「同一条候选在两个桶里」。
    """
    text = path.read_text(encoding="utf-8")
    marks = [(m.start(), m.group(1), m.group(2).strip())
             for m in CAND_HDR.finditer(text)]
    out = {}
    for i, (pos, cid, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = text[pos:end]
        pid = ""
        m = re.search(r"\|\s*池内编号\s*\|\s*\**P?(\d+)\**", body)
        if m:
            pid = "P" + m.group(1).zfill(4)
        m = re.search(r"\|\s*期次\s*\|\s*`?([0-9a-zA-Z]+)`?", body)
        eid = m.group(1) if m else ""
        m = re.search(r"\|\s*行情阶段\s*\|\s*\*{0,2}(R\d|U)", body)
        regime = m.group(1) if m else ""
        out[cid] = {"name": name, "pid": pid, "eid": eid, "regime": regime}
    return out


RECON_ROW = re.compile(r"^\|\s*([A-Z]\d{2}-\d{3}|[A-Z]\d{3,4})\s*\|(.*)$", re.M)


def parse_recon(path):
    """归并产出：候选编号 → 落点规则编号"""
    text = path.read_text(encoding="utf-8")
    i = text.find("## 四")
    seg = text[i:] if i >= 0 else text
    out = {}
    for line in seg.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for k in range(len(cells) - 1):
            cid = cells[k]
            if not re.fullmatch(r"[A-Z]\d{2}-\d{3}|[A-Z]\d{3,4}", cid):
                continue
            dest = cells[k + 1]
            m = re.search(r"→\s*([A-Z]\d*[-M\d]*[A-Z]?|M\d+(?:-[A-Z])?|S\d+)", dest)
            out[cid] = m.group(1) if m else dest[:20]
    return out


def parse_rule_names(path):
    """归并产出：规则编号 → 规则名"""
    text = path.read_text(encoding="utf-8")
    i = text.find("## 二、")
    j = re.search(r"^## [三四]、", text[i:], re.M)
    seg = text[i:i + j.start()] if (i >= 0 and j) else text
    out = {}
    for m in re.finditer(r"^#{3,4}\s+([A-Z]\d*[-M\d]*[A-Z]?)\s*[·.]\s*(.+)$", seg, re.M):
        out.setdefault(m.group(1), m.group(2).strip())
    return out


def main():
    bucket_files = sorted(BUCKET_DIR.glob("*.md"))
    merge_files = sorted(MERGE_DIR.glob("*.md"))

    # ① 每个桶里有哪些候选
    #     ⚠️ 键必须是 (桶, 桶内编号)——桶内编号每个桶都从 001 重来，单独用它不唯一。
    cand_in_bucket = defaultdict(list)      # bucket → [cid]
    cand_meta = {}                          # (bucket, cid) → {name, pid, eid, regime}
    for f in bucket_files:
        bucket = f.stem.split("-")[0]
        for cid, meta in parse_candidates(f).items():
            cand_in_bucket[bucket].append(cid)
            cand_meta[(bucket, cid)] = meta

    # ② 每个桶把候选归到了哪条规则
    bucket_recon = defaultdict(dict)      # bucket → {cid: rule_id}
    rule_names = defaultdict(dict)        # bucket → {rule_id: name}
    for f in merge_files:
        bucket = f.stem.split("-")[0]
        bucket_recon[bucket] = parse_recon(f)
        rule_names[bucket] = parse_rule_names(f)

    n_pid = len({m.get("pid") for m in cand_meta.values() if m.get("pid")})
    print(f"桶 {len(cand_in_bucket)} 个 ｜ 桶内候选 {len(cand_meta):,} 条 ｜ "
          f"池内唯一候选 {n_pid:,} 条")
    print(f"归并产出 {len(bucket_recon)} 个 ｜ 规则节点 "
          f"{sum(len(v) for v in rule_names.values())} 个")

    # ③ 追踪：池内编号 → [(桶, 落点规则, 桶内编号)]
    pid_to_loc = defaultdict(list)
    pid_meta = {}
    for bucket, cids in cand_in_bucket.items():
        for cid in cids:
            meta = cand_meta[(bucket, cid)]
            pid = meta.get("pid")
            if not pid:
                continue
            pid_meta.setdefault(pid, meta)
            rid = bucket_recon.get(bucket, {}).get(cid)
            if rid:
                pid_to_loc[pid].append((bucket, rid, cid))

    # ④ 规则 → 它收了哪些池内编号
    rule_pids = defaultdict(set)
    for pid, locs in pid_to_loc.items():
        for bucket, rid, _cid in locs:
            rule_pids[(bucket, rid)].add(pid)

    # ⑤ 通过共享池内编号关联的规则（跨桶规则图）——这是精确关系，不是猜的
    pid_to_rules = defaultdict(set)
    for (bucket, rid), pids in rule_pids.items():
        for pid in pids:
            pid_to_rules[pid].add((bucket, rid))

    # ⑤b 规则对之间的共享候选数——这是最有区分度的信号
    #
    # 连通分量只能说明「整体连通」（出来一个 2,027 节点的大簇，没用）。
    # 真正有用的是**两两共享多少条候选**：
    #   共享 8 条 → 几乎肯定是同一条规则被两个桶从不同角度描述
    #   共享 1 条 → 只是偶然共用了一个跨主题的候选
    pair_share = defaultdict(set)
    for pid, rules in pid_to_rules.items():
        rl = sorted(rules)
        if len(rl) < 2:
            continue
        for i in range(len(rl)):
            for j in range(i + 1, len(rl)):
                pair_share[(rl[i], rl[j])].add(pid)

    strong_pairs = [(k, v) for k, v in pair_share.items() if len(v) >= SHARE_STRONG]
    strong_pairs.sort(key=lambda x: -len(x[1]))
    weak_pairs = [(k, v) for k, v in pair_share.items()
                  if len(v) == SHARE_WEAK]

    linked = defaultdict(set)
    for pid, rules in pid_to_rules.items():
        if len(rules) < 2:
            continue
        rl = sorted(rules)
        for i in range(len(rl)):
            for j in range(i + 1, len(rl)):
                linked[rl[i]].add(rl[j])
                linked[rl[j]].add(rl[i])

    # 连通分量 = 跨桶规则簇
    seen, clusters = set(), []
    for r in linked:
        if r in seen:
            continue
        stack, comp = [r], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.append(x)
            stack.extend(linked[x] - seen)
        if len(comp) > 1:
            clusters.append(comp)
    clusters.sort(key=lambda c: -len(c))

    # ⑥ 候选落进几个桶
    spread = defaultdict(int)
    for pid, locs in pid_to_loc.items():
        spread[len(locs)] += 1

    # ⑦ 只在单桶出现的候选
    solo_cands = [pid for pid, locs in pid_to_loc.items() if len(locs) == 1]

    print(f"\n有落点的池内候选：{len(pid_to_loc):,} 条")
    print(f"候选跨桶数分布：{dict(sorted(spread.items()))}")
    print(f"强关联规则对（共享 ≥{SHARE_STRONG} 条候选）：{len(strong_pairs)}")
    print(f"待确认规则对（共享 {SHARE_WEAK} 条）：{len(weak_pairs)}")
    print(f"连通簇：{len(clusters)} 个（最大 {max((len(c) for c in clusters), default=0)} 节点）")

    OUT_JSON.write_text(json.dumps({
        "buckets": len(cand_in_bucket),
        "bucket_candidates": len(cand_meta),
        "unique_candidates": n_pid,
        "traced": len(pid_to_loc),
        "rule_nodes": sum(len(v) for v in rule_names.values()),
        "clusters": len(clusters),
        "strong_pairs": len(strong_pairs),
        "weak_pairs": len(weak_pairs),
        "spread": dict(sorted(spread.items())),
        "strong_pair_detail": [
            {
                "shared": len(v),
                "a": {"id": f"{k[0][0]}/{k[0][1]}", "name": rule_names[k[0][0]].get(k[0][1], ""),
                      "cands": len(rule_pids[k[0]])},
                "b": {"id": f"{k[1][0]}/{k[1][1]}", "name": rule_names[k[1][0]].get(k[1][1], ""),
                      "cands": len(rule_pids[k[1]])},
                "pids": sorted(v)[:20],
            } for k, v in strong_pairs
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    L = []
    A = L.append
    A("# 线3 播客 · 候选级跨桶追踪")
    A("")
    A("> 生成：2026-11-02 ｜ 工具：`tools/candidate_trace.py`")
    A("")
    A("## 为什么不用文本相似度")
    A("")
    A("先试过用「触发+动作」的正文相似度找跨桶重复，只找到 37 对。但那不可靠——")
    A("同一条规则被不同桶从不同角度描述时，文字会差很远：")
    A("")
    A("```")
    A("止损桶：破位即止损，技术位失守就走，割错也走")
    A("减仓桶：破位就减仓/清仓，越过技术位即处置")
    A("```")
    A("")
    A("这两条是同一件事的两面（一个是「走不走」，一个是「走多少」），")
    A("但文字相似度只有 0.3 左右，会被漏掉。")
    A("")
    A("**正确做法：追池内编号。** 池内编号 P0002 是全局唯一的；")
    A("桶内编号（B01-001）是局部的——每个桶都从 001 重来，")
    A("所以 B01-001 和 B06-001 是完全不同的候选。")
    A("")
    A("第一版就栽在这里：9,762 条候选全部显示「跨 1 个桶」。")
    A("改用池内编号后，跨桶关系是**精确事实**，不需要猜。")
    A("")
    A("## 结果")
    A("")
    A("| 项 | 值 |")
    A("|---|---|")
    A(f"| 桶 | {len(cand_in_bucket)} |")
    A(f"| 桶内候选位置（含重复计入） | {len(cand_meta):,} |")
    A(f"| 池内唯一候选 | {n_pid:,} |")
    A(f"| 有落点的候选 | {len(pid_to_loc):,} |")
    A(f"| 规则节点 | {sum(len(v) for v in rule_names.values())} |")
    A(f"| **强关联规则对**（共享 ≥{SHARE_STRONG} 条候选） | **{len(strong_pairs)}** |")
    A(f"| 待确认规则对（共享 {SHARE_WEAK} 条） | {len(weak_pairs)} |")
    A(f"| 连通簇 | {len(clusters)} 个（最大 {max((len(c) for c in clusters), default=0)} 节点） |")
    A("")
    A("> **连通分量在这里没用**——出来一个 2,027 节点的大簇，只说明「整体连通」，")
    A("> 没有区分度。有用的信号是**两两共享多少条候选**：")
    A(f"> 共享 ≥{SHARE_STRONG} 条 → 几乎肯定是同一条规则被两个桶从不同角度描述；")
    A("> 共享 1 条 → 只是偶然共用了一个跨主题的候选。")
    A("")
    A("**候选跨桶数分布**（一条候选落进几个桶）：")
    A("")
    A("| 跨桶数 | 候选数 |")
    A("|---:|---:|")
    for k, v in sorted(spread.items()):
        A(f"| {k} | {v:,} |")
    A("")
    A(f"> 只在 1 个桶出现的候选：**{len(solo_cands):,}** 条——这些不涉及跨桶合并。")
    A("")
    A("---")
    A("")
    A(f"## 一、强关联规则对（共享 ≥{SHARE_STRONG} 条候选，最可信的跨桶重复）")
    A("")
    A("这些对几乎肯定是**同一条规则**被两个桶从不同角度描述。")
    A("组装时应当合并，并保留两个角度（如「走不走」与「走多少」）。")
    A("")
    A("| # | 共享 | 规则 A | 规则 B |")
    A("|---:|---:|---|---|")
    for i, (k, v) in enumerate(strong_pairs[:60], 1):
        a = f"{k[0][0]}/{k[0][1]} {rule_names[k[0][0]].get(k[0][1],'')[:38]}"
        b = f"{k[1][0]}/{k[1][1]} {rule_names[k[1][0]].get(k[1][1],'')[:38]}"
        A(f"| {i} | {len(v)} | {a} | {b} |")
    A("")
    A(f"> 共 {len(strong_pairs)} 对强关联")
    A("")
    A("---")
    A("")
    A("## 一之二、强关联明细（前 25 对）")
    A("")
    for i, (k, v) in enumerate(strong_pairs[:25], 1):
        A(f"### S{i:02d} · 共享 {len(v)} 条候选")
        A("")
        A(f"- **A** `{k[0][0]}/{k[0][1]}`（该规则共收 {len(rule_pids[k[0]])} 条候选）")
        A(f"  - {rule_names[k[0][0]].get(k[0][1],'')}")
        A(f"- **B** `{k[1][0]}/{k[1][1]}`（该规则共收 {len(rule_pids[k[1]])} 条候选）")
        A(f"  - {rule_names[k[1][0]].get(k[1][1],'')}")
        A(f"- **共享的候选**：{'、'.join(sorted(v)[:12])}")
        A("")
    A("---")
    A("")
    A("## 二、跨主题综合候选（落进 ≥5 个桶）")
    A("")
    A("这些候选同时命中多个主题，说明它们是**跨主题的综合规则**——")
    A("组装心智模型时，它们往往是模型之间的连接点。")
    A("")
    multi = [(pid, locs) for pid, locs in pid_to_loc.items() if len(locs) >= 5]
    multi.sort(key=lambda x: -len(x[1]))
    A("| 候选 | 规则名 | 跨桶 | 落点 |")
    A("|---|---|---:|---|")
    for pid, locs in multi[:60]:
        meta = pid_meta.get(pid, {})
        where = "、".join(f"{b}/{r}" for b, r, _ in locs[:6])
        A(f"| {pid} | {meta.get('name','')[:38]} | {len(locs)} | {where} |")
    A("")
    A(f"> 共 {len(multi)} 条跨 ≥5 桶的候选")
    A("")
    A("---")
    A("")
    A("## 三、下一步")
    A("")
    A("跨桶关系的可靠来源已经建立。接下来：")
    A("")
    A("1. 用簇把「同一件事的不同侧面」收拢成一条完整规则")
    A("2. 用跨主题候选找出心智模型之间的连接点")
    A("3. 把所有规则分配到心智模型下")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    print(f"→ {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())