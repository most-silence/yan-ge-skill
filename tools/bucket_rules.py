#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bucket_rules.py — 把 2,612 条候选按操作对象分桶

为什么先分桶而不是直接语义归并
------------------------------
规则名是批读员每批各自起的，同一条规则在 95 批里有 95 种说法：

    120 分钟 120-25 跌破，那个位置就不是博弈多头点，该止损就止损
    120 分钟破位 + 被套 + 弱势板块 → 该走就走

字面匹配抓不到，直接上 LLM 归并 2,612 条也不现实（上下文放不下，且无法复核）。
分桶把问题拆小：每桶几十到几百条，一个 subagent 能读完，产物可逐桶复核。

为什么按「操作对象」切而不是按「心智模型」切
--------------------------------------------
心智模型是归并的**产出**，不能当输入——那是循环依赖。
操作对象（止损/止盈/仓位/均线）是机械可判的，无循环依赖。
先出零件，再把零件组装成结构。

分桶规则
--------
一条候选可以同时落进多个桶（「120 分钟跌破就止损」既是均线也是止损）。
这是故意的——宁可重复，不可漏掉。归并阶段再去重。

用法
----
  python tools/bucket_rules.py
  python tools/bucket_rules.py --min 5    # 只输出 ≥5 条的桶
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL_JSON = ROOT / "sources" / "05-播客转写" / "_规则池.json"
OUT_DIR = ROOT / "sources" / "05-播客转写" / "_分桶"
OUT_INDEX = ROOT / "sources" / "05-播客转写" / "_分桶索引.md"

# ── 主题桶定义 ──
# (桶号, 桶名, 关键词列表, 说明)
# 关键词匹配范围：规则名 + 触发条件 + 动作 + 数字 + 原话
BUCKETS = [
    ("B01", "止损", ["止损", "割", "认赔", "砍掉", "走人", "离场", "不犹豫"], "什么时候认错离场"),
    ("B02", "止盈", ["止盈", "落袋", "赚钱就跑", "了结", "卖掉", "卖", "走一半", "减掉"], "什么时候兑现利润"),
    ("B03", "仓位分层", ["仓位", "成仓", "楼", "层仓", "满仓", "半仓", "零仓", "上仓位"], "用几成仓"),
    ("B04", "建仓", ["建仓", "开仓", "买入", "进场", "下手", "上仓位", "分批"], "怎么买进去"),
    ("B05", "加仓/补仓", ["加仓", "补仓", "摊薄", "补", "家仓", "再买"], "跌了要不要加"),
    ("B06", "减仓/清仓", ["减仓", "清仓", "降仓", "踢出去", "抛", "减掉", "走一部分"], "什么时候减"),
    ("B07", "空仓/不做", ["空仓", "不做", "空一点", "不买", "看着", "等", "不动"], "什么时候不参与"),
    ("B08", "均线系统", ["均线", "军线", "军衔", "5日", "20日", "99", "128", "225", "5天线", "20天线", "120分钟", "15分钟"], "五条均线怎么用"),
    ("B09", "量能", ["量能", "放量", "缩量", "亮能", "成交量", "成交额", "万亿", "量价"], "量价关系"),
    ("B10", "压力支撑", ["压力", "支撑", "点位", "位置", "关口", "整数", "箱体", "区间"], "关键价位"),
    ("B11", "形态/结构", ["形态", "筑底", "注底", "金针", "反包", "破位", "新低", "头肩", "箱体", "趋势"], "图形识别"),
    ("B12", "底部判断", ["底部", "抄底", "见底", "底部形成", "大底", "底"], "怎么认底部"),
    ("B13", "顶部判断", ["顶部", "见顶", "头部", "冲高", "高位", "逃顶"], "怎么认顶部"),
    ("B14", "反弹", ["反弹", "反抽", "回升", "反弹幅度", "反弹到"], "反弹怎么处理"),
    ("B15", "做T", ["做T", "高抛低吸", "T+0", "做 t", "倒梯", "差价"], "日内/短差"),
    ("B16", "追涨/位置感", ["追", "追涨", "高位", "位置", "错过", "不敢", "飞刀"], "能不能追"),
    ("B17", "板块/轮动", ["板块", "轮动", "题材", "方向", "小盘", "大盘股", "风格", "银行", "科技", "军工"], "选什么方向"),
    ("B18", "大盘/指数", ["大盘", "上证", "创业板", "深证", "科创", "指数", "大侠", "大海"], "看哪个指数"),
    ("B19", "多周期确认", ["15分钟", "60分钟", "120分钟", "周期", "级别", "日线", "周线"], "大小周期配合"),
    ("B20", "纪律/心态", ["纪律", "心态", "情绪", "耐心", "贪", "怕", "后悔", "慌", "老韭菜", "知行"], "心理与执行"),
    ("B21", "资金/主力", ["资金", "主力", "机构", "国家队", "进场", "出货", "北向"], "谁在买"),
    ("B22", "时间窗/日历", ["月", "号", "季节", "窗口", "年前", "月初", "周末", "时间节点", "会议"], "什么时点"),
    ("B23", "概率/胜率", ["概率", "胜率", "赔率", "盈亏比", "期望", "对错"], "怎么算账"),
    ("B24", "宏观/外围", ["外围", "美股", "美债", "汇率", "战争", "消息", "利好", "利空", "政策"], "外部环境"),
]


def load_rules():
    data = json.loads(POOL_JSON.read_text(encoding="utf-8"))
    rules = data["rules"]
    # 记下池内编号。跨桶追踪需要一个**跨桶恒定**的身份——
    # 桶内编号（B01-001）每个桶都从 001 重来，认不出「同一条候选在两个桶里」。
    # 池内编号是全局唯一的，写进桶文件就能精确追踪。
    for i, r in enumerate(rules):
        r["_pool_idx"] = i + 1
    return rules


def haystack(rule):
    """把一条规则里所有可搜的文本拼起来"""
    parts = [rule.get("name", "")]
    for ev in rule.get("evidence", []):
        parts.extend([
            ev.get("trigger", ""), ev.get("action", ""),
            ev.get("numbers", ""), ev.get("quote", ""),
        ])
    return " ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=1, help="只输出 ≥N 条的桶")
    args = ap.parse_args()

    rules = load_rules()
    print(f"读入 {len(rules)} 条候选")

    buckets = defaultdict(list)
    no_bucket = []
    for r in rules:
        text = haystack(r)
        hit = False
        for code, name, kws, _desc in BUCKETS:
            if any(k in text for k in kws):
                buckets[code].append(r)
                hit = True
        if not hit:
            no_bucket.append(r)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    index = []
    for code, name, kws, desc in BUCKETS:
        items = buckets.get(code, [])
        if len(items) < args.min:
            continue
        # 按跨阶段数 + 出现次数排序
        items.sort(key=lambda r: (-r.get("n_regimes", 0), -r.get("count", 1)))

        parts = []
        P = parts.append
        P(f"# 主题桶 {code} · {name}")
        P("")
        P(f"> 共 **{len(items)}** 条候选 ｜ 说明：{desc}")
        P(f"> 关键词：{'、'.join(kws)}")
        P("")
        P("---")
        P("")
        for i, r in enumerate(items, 1):
            regs = "/".join(r.get("regimes") or []) or "—"
            P(f"## {code}-{i:03d} · {r['name']}")
            P("")
            P(f"| 项 | 值 |")
            P(f"|---|---|")
            P(f"| 池内编号 | **P{r.get('_pool_idx', 0):04d}** |")
            P(f"| 出现 | {r.get('count',1)} 次 ｜ 跨 {r.get('n_regimes',0)} 个阶段（{regs}） |")
            ev = r.get("evidence") or []
            eids = sorted({e.get("eid", "") for e in ev if e.get("eid")})
            src_batches = sorted({e.get("batch", "") for e in ev if e.get("batch")})
            P(f"| 原批 | {'、'.join(src_batches)} |")
            P(f"| 期次 | {'、'.join(f'`{e}`' for e in eids[:6])}{f' 等 {len(eids)} 期' if len(eids)>6 else ''} |")
            P("")
            for j, e in enumerate(ev[:3], 1):
                if j > 1:
                    P(f"**证据 {j}**（`{e.get('date') or '无日期'}` `{e.get('eid')}` `[{e.get('ts')}]`）：")
                else:
                    P(f"**证据**（`{e.get('date') or '无日期'}` `{e.get('eid')}` `[{e.get('ts')}]`）：")
                P("")
                if e.get("trigger"):
                    P(f"- **触发**：{e['trigger'][:300]}")
                if e.get("action"):
                    P(f"- **动作**：{e['action'][:300]}")
                if e.get("numbers"):
                    P(f"- **数字**：{e['numbers'][:200]}")
                q = (e.get("quote") or "").replace("\n", " ")[:300]
                if q:
                    P(f"- **原话**：{q}")
                P("")
            P("---")
            P("")

        f = OUT_DIR / f"{code}-{name.replace('/', '_')}.md"
        f.write_text("\n".join(parts) + "\n", encoding="utf-8")
        index.append({
            "code": code, "name": name, "count": len(items),
            "file": f.name, "kb": round(f.stat().st_size / 1024),
            "desc": desc,
        })

    # 未分桶的
    if no_bucket:
        parts = ["# 未分桶候选", "", f"> **{len(no_bucket)}** 条没有命中任何桶的关键词。",
                 "", "这些可能是：① 跨主题的综合规则 ② 用词不在词表里的规则 ③ 纯 reference 性质",
                 "", "---", ""]
        for i, r in enumerate(no_bucket, 1):
            parts.append(f"## X{i:03d} · {r['name']}")
            parts.append("")
            ev = r.get("evidence") or []
            for e in ev[:2]:
                parts.append(f"- `{e.get('date') or '无日期'}` `{e.get('eid')}` `[{e.get('ts')}]`")
                if e.get("trigger"):
                    parts.append(f"  - 触发：{e['trigger'][:200]}")
                if e.get("action"):
                    parts.append(f"  - 动作：{e['action'][:200]}")
            parts.append("")
        (OUT_DIR / "X-未分桶.md").write_text("\n".join(parts) + "\n", encoding="utf-8")
        index.append({"code": "X", "name": "未分桶", "count": len(no_bucket),
                      "file": "X-未分桶.md", "kb": round((OUT_DIR / "X-未分桶.md").stat().st_size / 1024),
                      "desc": "关键词未命中"})

    (OUT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2),
                                        encoding="utf-8")

    # ── 索引 md ──
    L = []
    A = L.append
    A("# 线3 播客 · 主题分桶索引")
    A("")
    A("> 生成：2026-11-01 ｜ 工具：`tools/bucket_rules.py`")
    A(f"> 输入：{len(rules)} 条候选 ｜ 输出：{len(index)} 个桶")
    A("")
    A("## 为什么先分桶")
    A("")
    A("规则名是批读员每批各自起的，同一条规则在 95 批里有 95 种说法：")
    A("")
    A("```")
    A("120 分钟 120-25 跌破，那个位置就不是博弈多头点，该止损就止损")
    A("120 分钟破位 + 被套 + 弱势板块 → 该走就走")
    A("```")
    A("")
    A("字面匹配抓不到。直接让 LLM 归并 2,612 条也不现实——上下文放不下，且无法逐条复核。")
    A("分桶把问题拆小：每桶几十到几百条，一个 subagent 能读完，产物可逐桶复核。")
    A("")
    A("> **一条候选可以同时落进多个桶**（「120 分钟跌破就止损」既是均线也是止损）。")
    A("> 这是故意的——宁可重复，不可漏掉。归并阶段再去重。")
    A("")
    A("## 分桶结果")
    A("")
    A("| 桶 | 名称 | 候选数 | 说明 |")
    A("|---|---|---:|---|")
    for it in sorted(index, key=lambda x: -x["count"]):
        A(f"| **{it['code']}** | {it['name']} | {it['count']} | {it['desc']} |")
    A("")
    total_assigned = sum(it["count"] for it in index)
    A(f"> 分桶总和 **{total_assigned:,}** 条（含重复计入）｜ 原始 {len(rules):,} 条")
    A(f"> 平均每条落进 **{total_assigned / len(rules):.1f}** 个桶")
    A("")
    A("## 下一步")
    A("")
    A("每个桶交给一个独立 subagent 做**桶内语义归并**，产出：")
    A("")
    A("1. 这个主题下他到底有哪几条规则（把 N 种说法收成 M 条）")
    A("2. 每条规则挂上所有支持它的期次 + 跨阶段次数")
    A("3. 冲突保留（同一主题下的相反说法，两条都在）")
    A("")
    A("> 归并产物是「零件」，之后再把零件组装成「心智模型」——")
    A("> 顺序不能反。心智模型是归并的产出，不能当输入。")

    OUT_INDEX.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"\n分桶结果（{len(index)} 个桶）：")
    for it in sorted(index, key=lambda x: -x["count"]):
        print(f"  {it['code']} {it['name']:<12} {it['count']:>4} 条  {it['kb']:>4} KB")
    print(f"\n分桶总和 {total_assigned:,}（含重复）｜ 平均每条 {total_assigned/len(rules):.1f} 个桶")
    print(f"\n→ {OUT_INDEX.relative_to(ROOT)}")
    print(f"→ {OUT_DIR.relative_to(ROOT)}\\")
    return 0


if __name__ == "__main__":
    sys.exit(main())
