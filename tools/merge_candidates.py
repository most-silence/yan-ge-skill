#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""merge_candidates.py — 合并批读结果，跨批去重，生成统一候选池

为什么需要跨批去重
------------------
38 批 × 10 期，同一规则会在多个批次、多个行情阶段重复出现。这不是冗余，是证据：

  只在 1 个阶段出现 → 弱（可能只是当期观点）
  跨 2 个阶段出现   → 中（可能是方法）
  跨 ≥3 个阶段出现 → 强（是稳定的框架）

去重不是"删掉重复的"，而是**把重复次数变成证据强度**。
这正是女娲三重验证第一关「跨域复现」在本项目的落地形式。

输出
----
  sources/05-播客转写/_规则池.md      人读：按证据强度分级
  sources/05-播客转写/_规则池.json    机读：供后续 SKILL 构建

用法
----
  python tools/merge_candidates.py
  python tools/merge_candidates.py --strict   # 只输出跨≥2 阶段的
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND_DIR = ROOT / "sources" / "05-播客转写" / "_规则候选"
REGIME_JSON = ROOT / "sources" / "05-播客转写" / "_行情阶段.json"
OUT_MD = ROOT / "sources" / "05-播客转写" / "_规则池.md"
OUT_JSON = ROOT / "sources" / "05-播客转写" / "_规则池.json"

# 批读模板里的分节标记
SEC_A = re.compile(r"^##\s*A[.\s、]")
SEC_ANY = re.compile(r"^##\s*[A-E][.\s、]")
ITEM_A = re.compile(r"^###\s*A(\d+)\s*[·.\s]\s*(.+)$")

# 批读产出里所有可能的字段标签。它们标志着一个字段的开始，
# 也是上一个字段的结束——这是 extract_field 能正确切块的前提。
FIELD_LABELS = [
    "触发条件", "动作", "具体数字", "原话", "要素完备度",
    "我的判断", "为什么是 reference 不是 verified", "缺什么", "补读线索",
]


def extract_field(raw, label):
    """从一条候选的 raw 文本里抽出某个字段的正文

    为什么不能用一个简单正则
    ------------------------
    批读产出的排版不统一，同一个字段有四种写法：

        **触发条件**（什么情况下用）：
        要判断大资金是否进场时。                    ← 内容在下一行

        **触发条件**：要判断大资金是否进场时。       ← 内容在同一行

        **触发条件**（什么情况下用）：要判断……       ← 标签带括注 + 同行

        **触发条件**：
        第一行
        第二行                                       ← 内容跨多行

    第一版用了 `\\*\\*标签\\*\\*[^\\n]*\\n(.+?)(?=\\n\\*\\*|\\Z)`，假设内容必在下一行。
    结果「动作」这种同行写法的，正则从下一行开始抓，抓到了**下一个字段**的内容——
    于是 trigger 里装着动作，action 里装着数字，整条链错位一格。
    2,612 条候选全部受影响。

    正确做法：先定位标签位置，再从标签末尾抓到**下一个字段标签出现处**。
    """
    # 1. 找到本字段标签的位置（取第一个）
    m = re.search(r"\*\*" + re.escape(label) + r"\*\*", raw)
    if not m:
        return ""
    start = m.end()
    # 2. 跳过标签后的括注与冒号，例如「（什么情况下用）：」
    rest = raw[start:]
    skip = re.match(r"[^\n：:]{0,30}[：:]\s*", rest)
    if skip:
        start += skip.end()
    # 3. 找下一个字段标签的位置，作为结束锚点
    end = len(raw)
    tail = raw[start:]
    for other in FIELD_LABELS:
        if other == label:
            continue
        om = re.search(r"\*\*" + re.escape(other) + r"\*\*", tail)
        if om and start + om.start() < end:
            end = start + om.start()
    body = raw[start:end]
    # 4. 去掉 markdown 引用/表格残留，压空白
    body = re.sub(r"^\s*\|\s*", "", body, flags=re.M)
    return re.sub(r"\s+", " ", body).strip().strip("|").strip()


def parse_batch(path):
    """解析一份批读产出，返回 verified 条目列表"""
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    # 只取 §A 段
    start = None
    end = len(lines)
    for i, ln in enumerate(lines):
        if SEC_A.match(ln):
            start = i
            continue
        if start is not None and i > start and SEC_ANY.match(ln):
            end = i
            break
    if start is None:
        return []

    body = lines[start:end]

    items, cur = [], None
    for ln in body:
        m = ITEM_A.match(ln.strip())
        if m:
            if cur:
                items.append(cur)
            cur = {"no": m.group(1), "name": m.group(2).strip(), "raw": [ln]}
        elif cur is not None:
            cur["raw"].append(ln)
    if cur:
        items.append(cur)

    out = []
    for it in items:
        raw = "\n".join(it["raw"])
        rec = {"no": it["no"], "name": it["name"], "batch": path.stem}

        # 期次
        m = re.search(r"\|\s*期次\s*\|\s*`?([0-9a-zA-Z]+)`?\s*\|", raw)
        rec["eid"] = m.group(1) if m else ""
        # 日期
        m = re.search(r"\|\s*日期\s*\|\s*(\d{4}-\d{2}-\d{2})", raw)
        rec["date"] = m.group(1) if m else ""
        # 行情阶段
        m = re.search(r"\|\s*行情阶段\s*\|\s*\*{0,2}(R\d|U)", raw)
        rec["regime"] = m.group(1) if m else ""
        # 时间戳
        m = re.search(r"\|\s*时间戳\s*\|\s*`?\[(\d{2}:\d{2}:\d{2})\]`?", raw)
        rec["ts"] = m.group(1) if m else ""
        # 类型
        m = re.search(r"\|\s*类型\s*\|\s*([a-zA-Z_ /]+)", raw)
        rec["type"] = m.group(1).strip() if m else ""

        # 触发条件 / 动作 / 数字 三个正文块
        for key, label in (
            ("trigger", "触发条件"),
            ("action", "动作"),
            ("numbers", "具体数字"),
        ):
            rec[key] = extract_field(raw, label)

        # 原话
        m = re.search(r"\*\*原话\*\*[^\n]*\n((?:>.*\n?)+)", raw)
        rec["quote"] = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

        # 要素完备度
        m = re.search(r"\*\*要素完备度\*\*[^\n]*\n?(.+)", raw)
        rec["completeness"] = m.group(1).strip() if m else ""

        rec["raw"] = raw
        out.append(rec)
    return out


def normalize(name):
    """把规则名归一到可比较的key

    批读者会写「止损线到了就卖」和「到止损线必须离场」——语义同一，字面不同。
    这里只做粗归一：去标点、去修饰词。真正的语义合并留给人工确认。
    """
    s = re.sub(r"[，。、·\s（）()【】\[\]]", "", name)
    for w in ("必须", "应该", "就要", "就要", "一定", "要", "就"):
        s = s.replace(w, "")
    return s[:20]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="只输出跨 ≥2 阶段的规则")
    ap.add_argument("--min-regimes", type=int, default=1)
    args = ap.parse_args()

    reg = json.loads(REGIME_JSON.read_text(encoding="utf-8"))
    eid2meta = {e["eid"]: e for e in reg["episodes"]}
    eid2meta.update({e["eid"]: e for e in reg["undated"]})

    files = sorted(CAND_DIR.glob("batch-*.md"))
    if not files:
        print(f"{CAND_DIR} 下没有 batch-*.md", file=sys.stderr)
        return 1

    all_items = []
    for p in files:
        items = parse_batch(p)
        for it in items:
            # 补齐阶段（批读可能漏填，用 eid 查）
            if not it["regime"] and it["eid"] in eid2meta:
                it["regime"] = eid2meta[it["eid"]].get("regime", "")
            if not it["date"] and it["eid"] in eid2meta:
                it["date"] = eid2meta[it["eid"]].get("date", "")
            all_items.append(it)

    # 粗归一分组
    groups = defaultdict(list)
    for it in all_items:
        groups[normalize(it["name"])].append(it)

    # 每组算证据强度
    merged = []
    for key, items in groups.items():
        regimes = sorted({i["regime"] for i in items if i["regime"]})
        eids = sorted({i["eid"] for i in items if i["eid"]})
        batches = sorted({i["batch"] for i in items})
        merged.append({
            "key": key,
            "name": items[0]["name"],
            "count": len(items),
            "regimes": regimes,
            "n_regimes": len(regimes),
            "eids": eids,
            "batches": batches,
            "items": items,
            "strength": ("强" if len(regimes) >= 3 else
                         "中" if len(regimes) == 2 else
                         "弱" if len(regimes) == 1 else "待定"),
        })
    merged.sort(key=lambda g: (-g["n_regimes"], -g["count"], g["name"]))

    kept = [g for g in merged if g["n_regimes"] >= args.min_regimes]

    # 统计
    strength_cnt = Counter(g["strength"] for g in merged)
    noise = Counter()
    for p in files:
        t = p.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"约\s*(\d+)\s*%", t)
        if m:
            noise[p.stem] = int(m.group(1))

    OUT_JSON.write_text(json.dumps({
        "generated": "2026-10-31",
        "batches_read": len(files),
        "items_total": len(all_items),
        "groups": len(merged),
        "strength": dict(strength_cnt),
        "rules": [
            {k: v for k, v in g.items() if k != "items"}
            | {"evidence": [
                {"batch": i["batch"], "eid": i["eid"], "date": i["date"],
                 "regime": i["regime"], "ts": i["ts"], "quote": i["quote"],
                 "trigger": i["trigger"], "action": i["action"],
                 "numbers": i["numbers"]}
                for i in g["items"]
            ]}
            for g in kept
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── MD ──
    L = []
    A = L.append
    A("# 线3 播客 · 规则候选池")
    A("")
    A(f"> 生成：2026-10-31 ｜ 工具：`tools/merge_candidates.py`")
    A(f"> 已读批次：**{len(files)} / 38** ｜ 原始候选：**{len(all_items)}** 条 "
      f"｜ 归并后：**{len(merged)}** 组")
    A("")
    A("## 一、证据强度怎么算")
    A("")
    A("女娲三重验证第一关是**跨域复现**。本项目语料是单一人的连续日更，")
    A("所以把「跨域」重新定义为**跨行情阶段**——同一规则在涨、跌、横盘不同环境下都出现，才算稳固。")
    A("")
    A("| 强度 | 判据 | 含义 |")
    A("|---|---|---|")
    A("| **强** | 跨 ≥3 个行情阶段 | 是稳定的框架，不是当期观点 |")
    A("| **中** | 跨 2 个阶段 | 可能是方法，需再验 |")
    A("| **弱** | 只在 1 个阶段出现 | 可能只是当期盘面评论 |")
    A("| 待定 | 无日期（70 期） | 无法挂阶段，不参与强度判定 |")
    A("")
    A("### 当前分布")
    A("")
    A("| 强度 | 组数 |")
    A("|---|---:|")
    for k in ("强", "中", "弱", "待定"):
        A(f"| {k} | {strength_cnt.get(k, 0)} |")
    A("")
    if noise:
        avg = sum(noise.values()) / len(noise)
        A(f"**噪音占比（批读自报均值）**：约 {avg:.0f}%")
        A("")
    A("## 二、按强度分级")
    A("")
    for strength in ("强", "中", "弱", "待定"):
        gs = [g for g in kept if g["strength"] == strength]
        if not gs:
            continue
        A(f"### {strength}（{len(gs)} 组）")
        A("")
        for g in gs:
            A(f"#### {g['name']}")
            A("")
            A(f"- **出现次数**：{g['count']} 次 ｜ **阶段**：{'/'.join(g['regimes']) or '—'} "
              f"｜ **期数**：{len(g['eids'])} 期 ｜ **批次**：{', '.join(g['batches'][:6])}")
            for i, ev in enumerate(g["items"][:4], 1):
                A(f"  {i}. `{ev['date'] or '无日期'}` `{ev['ts']}` — {ev['quote'][:150]}")
            if len(g["items"]) > 4:
                A(f"  …还有 {len(g['items']) - 4} 条证据，见 `_规则池.json`")
            A("")
    A("---")
    A("")
    A("> **合规**：本文件仅为研究学习其公开表达，不构成投资建议。**股市有风险，投资需谨慎。**")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"读 {len(files)} 批 / 原始候选 {len(all_items)} 条 / 归并 {len(merged)} 组")
    for k in ("强", "中", "弱", "待定"):
        print(f"  {k}: {strength_cnt.get(k, 0)} 组")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    print(f"→ {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
