#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coverage_audit.py — 覆盖率审计表（仓颉式两级台账）

为什么必须有这张表
------------------
它是**全量扫描**相对**抽样**的核心价值，也是 Q10 阴性证据校验的前提。

没有这张表，「他没讲过 X」这个结论无法成立——因为你不知道扫没扫到。
抽样后你连「不知道什么」都不知道。

结构（wisp 阶段1.5 的两级台账，映射到本项目的对象）
----------------------------------------------------

  用户任务 → 挂载期次（母本节点） → 候选 → decision → 最终去向
     ↑              ↑                  ↑         ↑          ↑
  他会问什么    他在哪期讲过      抽出的规则   四类分级   进 SKILL 哪节

四类去向（缺一不可，缺了审计链就断）
-----------------------------------
  verified     / reference / needs_review / rejected

用法
----
  python tools/coverage_audit.py
  python tools/coverage_audit.py --check   # 只做完整性检查，不出 md
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL_JSON = ROOT / "sources" / "05-播客转写" / "_规则池.json"
SKILL_MD = ROOT / "SKILL.md"
OUT_MD = ROOT / "sources" / "05-播客转写" / "_覆盖率审计.md"

# ── 用户任务清单 ──
# 来源：references/盲评题库.md 的 A/B/D 类 + SKILL.md「回答工作流」Step 1 的问题分类
# 这些是「用户真的会问的问题」，不是「我想抽的规则」。
# 每条任务必须能挂到一个或多个期次，否则就是明确的缺口。
TASKS = [
    ("T01", "手上的票跌破关键均线了，要不要走", "止损判断"),
    ("T02", "均线参数怎么设，能不能直接用 20 日线", "方法参数"),
    ("T03", "这票基本面怎么样，值不值得长拿", "基本面"),
    ("T04", "该用几成仓位买", "仓位"),
    ("T05", "要不要设止损，亏 8% 了", "风控"),
    ("T06", "什么时候该空仓不做", "择时/纪律"),
    ("T07", "加杠杆吗，连续亏三把怎么办", "极端/风控"),
    ("T08", "连续三个跌停怎么办", "极端行情"),
    ("T09", "黑天鹅爆出来全仓被埋", "极端行情"),
    ("T10", "大盘崩了是不是该清仓", "择时"),
    ("T11", "怎么判断一波反弹能到哪", "目标位"),
    ("T12", "放量和缩量到底怎么看", "量能"),
    ("T13", "什么形态算底部形成了", "形态"),
    ("T14", "追涨行不行，高位了还能不能进", "位置感"),
    ("T15", "做 T 怎么做，什么位置进什么位置出", "做T"),
    ("T16", "盈亏比和胜率怎么权衡", "概率"),
    ("T17", "亏了要不要补仓摊薄成本", "补仓"),
    ("T18", "什么时候该止盈，赚多少走", "止盈"),
    ("T19", "板块怎么轮动，怎么选方向", "板块"),
    ("T20", "利好出来为什么不涨", "归因"),
    ("T21", "外围大跌 A 股跟不跟", "宏观/外围"),
    ("T22", "大盘和个股不同步怎么办", "结构"),
    ("T23", "怎么看主力资金进没进场", "资金"),
    ("T24", "新手最容易犯什么错", "认知"),
    ("T25", "做股票这么多年图啥", "心态"),
]


def load_pool():
    if not POOL_JSON.exists():
        print(f"缺 {POOL_JSON.name}，先跑 merge_candidates.py", file=sys.stderr)
        return None
    return json.loads(POOL_JSON.read_text(encoding="utf-8"))


def match_task(task_name, keywords, rules):
    """把一条任务挂到规则池里的候选

    匹配方式：任务关键词在规则的 name / trigger / action / quote 里出现。
    这是机械匹配，会漏也会多——所以结果标「机械匹配」，人工要在后面复核。
    """
    kws = [k for k in re.split(r"[，、,/\s]+", keywords) if k]
    hits = []
    for r in rules:
        blob = " ".join([
            r.get("name", ""),
            r.get("evidence", [{}])[0].get("trigger", "") if r.get("evidence") else "",
            r.get("evidence", [{}])[0].get("action", "") if r.get("evidence") else "",
            " ".join(e.get("quote", "") for e in (r.get("evidence") or [])[:3]),
        ])
        if any(k in blob for k in kws):
            hits.append(r)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    pool = load_pool()
    if pool is None:
        return 1

    rules = pool["rules"]
    strength_cnt = Counter(r["strength"] for r in rules)

    # 逐任务匹配
    rows = []
    for code, task, kw in TASKS:
        hits = match_task(task, kw, rules)
        n_strong = sum(1 for h in hits if h["strength"] == "强")
        n_mid = sum(1 for h in hits if h["strength"] == "中")
        n_weak = sum(1 for h in hits if h["strength"] == "弱")
        regimes = sorted({rg for h in hits for rg in h["regimes"]})
        rows.append({
            "code": code, "task": task, "kw": kw,
            "n_rules": len(hits),
            "n_strong": n_strong, "n_mid": n_mid, "n_weak": n_weak,
            "regimes": regimes,
            "names": [h["name"] for h in hits[:5]],
        })

    covered = [r for r in rows if r["n_rules"] > 0]
    gaps = [r for r in rows if r["n_rules"] == 0]
    thin = [r for r in rows if 0 < r["n_rules"] < 2]

    if args.check:
        print(f"任务 {len(TASKS)} 条 ｜ 有候选 {len(covered)} ｜ 零候选 {len(gaps)}")
        if gaps:
            print("零候选任务：")
            for g in gaps:
                print(f"  {g['code']} {g['task']}")
        if thin:
            print("候选过少（<2 条）：")
            for t in thin:
                print(f"  {t['code']} {t['task']}  {t['n_rules']} 条")
        return 0

    # ── MD ──
    L = []
    A = L.append
    A("# 线3 播客 · 覆盖率审计表")
    A("")
    A("> 生成：2026-10-31 ｜ 工具：`tools/coverage_audit.py`")
    A("> 依据：仓颉 RIA-TV++ `references/methodology/03b-stage1.6-promotion-gate.md` 的两级台账")
    A("")
    A("## 为什么必须有这张表")
    A("")
    A("**它是全量扫描相对抽样的唯一硬价值，也是 Q10 阴性证据校验的前提。**")
    A("")
    A("玟火 Q10 要求在说「他没讲过 X」之前必须过四类词检索 + 全文分段读完。")
    A("抽样做不到这一点——抽样之后你连「不知道什么」都不知道，")
    A("于是「没扫到」会被误记成「他没讲」，产生**假边界**。")
    A("")
    A("> QC 原文：「假边界比编造更隐蔽，因为读者无从起疑。」")
    A("")
    A("## 一、台账结构")
    A("")
    A("```")
    A("用户任务 → 挂载期次（母本节点） → 候选 → decision → 最终去向")
    A("   ↑              ↑                 ↑        ↑          ↑")
    A("他会问什么    他在哪期讲过      抽出的规则  四类分级   进 SKILL 哪节")
    A("```")
    A("")
    A("## 二、审计总表")
    A("")
    A(f"> 规则池：**{pool['groups']} 组**（强 {strength_cnt.get('强',0)} / 中 {strength_cnt.get('中',0)} / "
      f"弱 {strength_cnt.get('弱',0)} / 待定 {strength_cnt.get('待定',0)}）")
    A(f"> 已读批次：**{pool['batches_read']} / 38**")
    A("")
    A("| # | 用户任务 | 候选数 | 强 | 中 | 弱 | 跨阶段 | 状态 | 代表规则 |")
    A("|---|---|---:|---:|---:|---:|---|---|---|")
    for r in rows:
        if r["n_rules"] == 0:
            status = "🔴 **零候选**"
        elif r["n_strong"] >= 1:
            status = "🟢 充足"
        elif r["n_rules"] >= 2:
            status = "🟡 偏薄"
        else:
            status = "🟠 单条"
        regs = "/".join(r["regimes"][:4]) or "—"
        names = "；".join(r["names"][:2])[:56] or "—"
        A(f"| {r['code']} | {r['task']} | {r['n_rules']} | {r['n_strong']} | {r['n_mid']} "
          f"| {r['n_weak']} | {regs} | {status} | {names} |")
    A("")
    A("### 汇总")
    A("")
    A("| 状态 | 任务数 | 含义 |")
    A("|---|---:|---|")
    A(f"| 🟢 充足（有强候选） | {sum(1 for r in rows if r['n_strong'] >= 1)} | 可以写进 SKILL |")
    A(f"| 🟡 偏薄（≥2 条但无强） | {sum(1 for r in rows if r['n_rules'] >= 2 and r['n_strong'] == 0)} | 能写但需标注证据不足 |")
    A(f"| 🟠 单条 | {sum(1 for r in rows if r['n_rules'] == 1)} | 单点证据，不能推成规则 |")
    A(f"| 🔴 零候选 | {len(gaps)} | **明确缺口，不是「他没讲过」** |")
    A("")
    if gaps:
        A("## 三、零候选任务（重要）")
        A("")
        A("这些任务在已读批次里**一条候选都没有**。两种可能，必须区分：")
        A("")
        A("| 可能 | 怎么判 | 处置 |")
        A("|---|---|---|")
        A("| ① 还没读到（批读未完成） | 等全部 38 批读完再复查 | 暂时标「待补」 |")
        A("| ② 真的没讲过 | 必须过 Q10 四类词检索 + 全文分段 | 写进诚实边界，附检索记录 |")
        A("")
        for g in gaps:
            A(f"- **{g['code']}** {g['task']}（关键词：{g['kw']}）")
        A("")
        A("> ⚠️ **不许在这一步就写「他没讲过」。** 批读每完成一批都要重跑本工具。")
        A("> 全部读完复查仍为零，才进 Q10 四类词检索流程。")
        A("")
    A("## 四、对照：现有 SKILL.md 的覆盖")
    A("")
    if SKILL_MD.exists():
        skill = SKILL_MD.read_text(encoding="utf-8")
        A("| # | 用户任务 | SKILL.md 是否涉及 |")
        A("|---|---|---|")
        for r in rows:
            hit = any(k in skill for k in re.split(r"[，、,/\s]+", r["kw"]))
            A(f"| {r['code']} | {r['task']} | {'✅ 有' if hit else '❌ 无'} |")
        A("")
        A("> 这一列只做**关键词命中**粗判，不代表 SKILL.md 真的答得了这个问题。")
        A("> 精确判断要看 SKILL.md 的「诚实边界」章节 + 盲评结果。")
    A("")
    A("---")
    A("")
    A("> **合规**：本文件仅为研究学习其公开表达，不构成投资建议。**股市有风险，投资需谨慎。**")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"任务 {len(TASKS)} ｜ 有候选 {len(covered)} ｜ 零候选 {len(gaps)} ｜ 偏薄 {len(thin)}")
    for g in gaps:
        print(f"  🔴 {g['code']} {g['task']}")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
