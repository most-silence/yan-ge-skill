#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""prescan_rules.py — 全量机械预筛：为批读生成候选地图

定位
----
这是 **A 档**（机械预筛）。它不能替代批读，作用是给批读画地图：

  A 档机械预筛（本脚本，覆盖 379/379，秒级）
    → B 档全量批读（25 批，独立 subagent 逐批抽规则）
      → C 档深度精读（长稿与 needs_review 二次细读）

为什么不能只靠机械预筛
----------------------
规则常跨段。「如果……那么……」中间隔十句是常态，滑窗只能抓到同段共现的那部分。
反过来，只靠批读不看预筛也不行——长稿里 42% 是闲聊，盲读会稀释注意力。

预筛的价值：**告诉批读者这一期哪几分钟值得细看**，把注意力集中到有信号的区间。

判定逻辑（三档）
----------------
  宽档 W：触发词 + 动作词 共现（滑窗 3 行）
  中档 M：宽档 + 出现具体数字（点位/百分比/金额/天数）
  强档 S：中档 + 同时出现风控词（止损/仓位/止盈/空仓）

用法
----
  python tools/prescan_rules.py
  python tools/prescan_rules.py --window 4 --out xxx.md
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = ROOT / "sources" / "05-播客转写" / "audio_txt"
REGIME_JSON = ROOT / "sources" / "05-播客转写" / "_行情阶段.json"
OUT_MD = ROOT / "sources" / "05-播客转写" / "_预筛地图.md"
OUT_JSON = ROOT / "sources" / "05-播客转写" / "_预筛地图.json"

# ── 触发词：条件从句的入口 ──
TRIGGERS = [
    "如果", "一旦", "只要", "除非", "假设", "要是", "万一",
    "跌破", "站上", "突破", "到位", "到了", "出现", "放量", "缩量",
    "超过", "低于", "之前", "之后", "的时候", "情况下",
]

# ── 动作词：他给出的处置动作 ──
ACTIONS = [
    "止损", "减仓", "加仓", "清仓", "空仓", "建仓", "补仓", "止盈",
    "卖掉", "卖出", "买入", "换成", "降仓", "持有", "离场", "走人",
    "减掉", "先撤", "落袋", "咬一口", "上仓位", "留着", "砍掉",
]

# ── 风控词：出现即高价值（风控是他的硬缺口） ──
RISK = ["止损", "止盈", "仓位", "仓", "亏", "赔", "风险", "回撤", "保护", "扛"]

# ── 数字：可验证的量
# ⚠️ 排除「年」和「月」：全量扫描发现「4000年」是「4000点」的 ASR 误听，
# 而「2024年10月8号」是真年份。两类混在一个正则里会互相污染。
# 把「N年→N点」单独立为 YEAR_POINT_RE，作为独立标记输出，不混进 num 字段。
NUM_RE = re.compile(
    r"\d+(?:\.\d+)?\s*"
    r"(?:%|％|个点|点|万亿|亿|万|倍|成|层|天|周|手|块钱|元)"
)

# 点位被听成「年」：3–5 位数字 + 年，且不是 19xx/20xx 年份
YEAR_POINT_RE = re.compile(r"(?<![\d.])(\d{3,5})\s*年")
_YEAR_OK = re.compile(r"^(19|20)\d{2}$")
_LINE_RE_CMT = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$")

# ── 行情词：确认这段在讲市场而非闲聊 ──
MARKET = [
    "大盘", "上证", "创业板", "深证", "科创", "指数", "压力位", "支撑位",
    "均线", "量能", "成交额", "点位", "开盘", "收盘", "午盘", "尾盘",
]

LINE_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$")


def load_episodes():
    """读阶段标注，拿 eid → (title, date, regime, dur_min)"""
    data = json.loads(REGIME_JSON.read_text(encoding="utf-8"))
    meta = {}
    for e in data["episodes"]:
        meta[e["eid"]] = {
            "title": e["title"], "date": e["date"],
            "regime": e["regime"], "dur_min": e["dur_min"],
        }
    for e in data["undated"]:
        meta[e["eid"]] = {
            "title": e["title"], "date": "", "regime": "U",
            "dur_min": e["dur_min"],
        }
    return meta


def parse_episode(path):
    """返回 [(时间戳, 正文)]，跳过元信息头"""
    out, started = [], False
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ln.strip() == "---":
            started = True
            continue
        if not started:
            continue
        m = LINE_RE.match(ln)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def scan_episode(lines, window):
    """滑窗扫描，返回命中窗口列表"""
    hits = []
    n = len(lines)
    for i in range(n):
        chunk = lines[i:i + window]
        text = " ".join(x[1] for x in chunk)
        t_hit = [k for k in TRIGGERS if k in text]
        a_hit = [k for k in ACTIONS if k in text]
        if not t_hit or not a_hit:
            continue
        r_hit = [k for k in RISK if k in text]
        m_hit = [k for k in MARKET if k in text]
        nums = NUM_RE.findall(text)
        # 点位被听成「年」的，单列标记，供数字对账阶段重点核
        yr = [f"{m}年→{m}点?" for m in YEAR_POINT_RE.findall(text)
              if not _YEAR_OK.match(m)]

        if (nums or yr) and r_hit:
            tier = "S"
        elif nums or yr:
            tier = "M"
        else:
            tier = "W"

        hits.append({
            "ts": chunk[0][0],
            "ts_end": chunk[-1][0],
            "tier": tier,
            "text": text.strip(),
            "triggers": sorted(set(t_hit)),
            "actions": sorted(set(a_hit)),
            "risk": sorted(set(r_hit)),
            "market": sorted(set(m_hit)),
            "nums": sorted(set(x.strip() for x in nums)),
            "year_point_suspect": sorted(set(yr)),
        })
    return hits


def dedupe(hits):
    """相邻/重叠窗口合并：同一时间戳只留 tier 最高的那条

    滑窗会让同一句话在多个窗口里重复出现。去重规则：
    - 起始时间戳相同 → 留 tier 最高、正文最长的
    - 其余保留（不同起始点意味着不同语境）
    """
    order = {"S": 0, "M": 1, "W": 2}
    best = {}
    for h in hits:
        k = h["ts"]
        cur = best.get(k)
        if cur is None:
            best[k] = h
            continue
        if (order[h["tier"]], -len(h["text"])) < (order[cur["tier"]], -len(cur["text"])):
            best[k] = h
    return sorted(best.values(), key=lambda x: x["ts"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=3, help="滑窗行数（默认 3）")
    args = ap.parse_args()

    meta = load_episodes()
    files = sorted(p for p in TXT_DIR.glob("*._clean.txt"))
    if not files:
        print("找不到 *._clean.txt，先跑 check_transcript.py --fix", file=sys.stderr)
        return 1

    per_ep = {}
    tier_total = Counter()
    trig_total = Counter()
    act_total = Counter()
    yr_total = 0

    for p in files:
        eid = p.name.split("_")[0]
        lines = parse_episode(p)
        hits = dedupe(scan_episode(lines, args.window))
        per_ep[eid] = {"lines": len(lines), "hits": hits}
        for h in hits:
            tier_total[h["tier"]] += 1
            trig_total.update(h["triggers"])
            act_total.update(h["actions"])
            yr_total += len(h.get("year_point_suspect") or [])

    # ── 汇总统计 ──
    total_hits = sum(tier_total.values())
    total_lines = sum(v["lines"] for v in per_ep.values())
    total_chars = sum(len(h["text"]) for v in per_ep.values() for h in v["hits"])
    eps_with = sum(1 for v in per_ep.values() if v["hits"])

    # 按阶段聚合
    by_regime = defaultdict(lambda: {"eps": 0, "hits": 0, "S": 0, "M": 0, "W": 0})
    for eid, v in per_ep.items():
        r = meta.get(eid, {}).get("regime", "?")
        by_regime[r]["eps"] += 1
        by_regime[r]["hits"] += len(v["hits"])
        for h in v["hits"]:
            by_regime[r][h["tier"]] += 1

    OUT_JSON.write_text(json.dumps({
        "generated": "2026-10-31",
        "window": args.window,
        "totals": {
            "episodes": len(per_ep),
            "episodes_with_hits": eps_with,
            "lines": total_lines,
            "hits": total_hits,
            "hits_S": tier_total["S"],
            "hits_M": tier_total["M"],
            "hits_W": tier_total["W"],
            "hit_chars": total_chars,
            "year_point_suspect": yr_total,
        },
        "by_regime": {k: dict(v) for k, v in by_regime.items()},
        "top_triggers": dict(trig_total.most_common(20)),
        "top_actions": dict(act_total.most_common(20)),
        "episodes": {
            eid: {
                "title": meta.get(eid, {}).get("title", ""),
                "date": meta.get(eid, {}).get("date", ""),
                "regime": meta.get(eid, {}).get("regime", "?"),
                "lines": v["lines"],
                "hits": v["hits"],
            }
            for eid, v in per_ep.items()
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── MD ──
    L = []
    A = L.append
    A("# 线3 播客 · A 档机械预筛地图")
    A("")
    A("> 生成：2026-10-31 ｜ 工具：`tools/prescan_rules.py --window 3`")
    A("> 覆盖：**379/379 期全量**（清洗稿）｜ 零流量")
    A("")
    A("## 一、这个文件是什么，不是什么")
    A("")
    A("**是**：批读阶段的注意力地图。告诉你哪一期、哪一分钟值得细看。")
    A("")
    A("**不是**：规则清单。机械预筛抓不到跨段规则——")
    A("「如果……那么……」中间隔十句是常态，滑窗只能抓到同段共现的部分。")
    A("")
    A("> 三层结构：**A 机械预筛（本文件）→ B 全量批读 → C 深度精读**。")
    A("> A 是 B 的地图，B 是 C 的漏斗。三层都跑，缺一层就有盲区。")
    A("")
    A("## 二、判定三档")
    A("")
    A("| 档 | 条件 | 含义 |")
    A("|---|---|---|")
    A("| **S 强** | 触发词 + 动作词 + **具体数字** + **风控词** | 最可能是可执行规则，优先细读 |")
    A("| **M 中** | 触发词 + 动作词 + 具体数字 | 可能是规则，但缺风控语境 |")
    A("| **W 宽** | 触发词 + 动作词 | 可能只是顺口带过，需看上下文 |")
    A("")
    A("### 词表（可复跑调整）")
    A("")
    A(f"- **触发词**（{len(TRIGGERS)} 个）：{'、'.join(TRIGGERS)}")
    A(f"- **动作词**（{len(ACTIONS)} 个）：{'、'.join(ACTIONS)}")
    A(f"- **风控词**（{len(RISK)} 个）：{'、'.join(RISK)}")
    A(f"- **行情词**（{len(MARKET)} 个）：{'、'.join(MARKET)}")
    A("- **数字正则**：`\\d+(\\.\\d+)?\\s*(%|个点|点|万亿|亿|万|倍|成|层|天|周|月|年|手|元)`")
    A("")
    A("## 三、总量")
    A("")
    A("| 指标 | 值 |")
    A("|---|---:|")
    A(f"| 扫描期数 | **{len(per_ep)}** |")
    A(f"| 有命中的期数 | **{eps_with}**（{eps_with / len(per_ep) * 100:.0f}%） |")
    A(f"| 正文行数 | {total_lines:,} |")
    A(f"| 命中窗口 | **{total_hits:,}** |")
    A(f"| ├ S 强 | **{tier_total['S']:,}** |")
    A(f"| ├ M 中 | {tier_total['M']:,} |")
    A(f"| └ W 宽 | {tier_total['W']:,} |")
    A(f"| 命中窗口总字数 | {total_chars:,}（约占全量 4,915,561 字的 {total_chars / 4915561 * 100:.1f}%） |")
    A("")
    A("### 按行情阶段")
    A("")
    A("| 阶段 | 期数 | 命中 | S | M | W | 每期均命中 |")
    A("|---|---:|---:|---:|---:|---:|---:|")
    for code in ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "U"]:
        v = by_regime.get(code)
        if not v or not v["eps"]:
            continue
        avg = v["hits"] / v["eps"]
        A(f"| {code} | {v['eps']} | {v['hits']:,} | {v['S']:,} | {v['M']:,} | {v['W']:,} | {avg:.1f} |")
    A("")
    A("### 高频触发词 / 动作词")
    A("")
    A("| 触发词 | 次数 | | 动作词 | 次数 |")
    A("|---|---:|---|---|---:|")
    tt = trig_total.most_common(12)
    at = act_total.most_common(12)
    for i in range(max(len(tt), len(at))):
        t = f"{tt[i][0]} | {tt[i][1]}" if i < len(tt) else " | "
        a = f"{at[i][0]} | {at[i][1]}" if i < len(at) else " | "
        A(f"| {t} | | {a} |")
    A("")
    A("## 四、S 强档全表（优先细读对象）")
    A("")
    A("> 按 S 命中数降序。这是 B 档批读的第一优先级。")
    A("")
    ranked = sorted(
        ((eid, v) for eid, v in per_ep.items()),
        key=lambda x: -sum(1 for h in x[1]["hits"] if h["tier"] == "S"),
    )
    A("| # | 日期 | 阶段 | 时长 | S | M | W | 标题 |")
    A("|---:|---|---|---:|---:|---:|---:|---|")
    for i, (eid, v) in enumerate(ranked[:60], 1):
        m = meta.get(eid, {})
        s = sum(1 for h in v["hits"] if h["tier"] == "S")
        mm = sum(1 for h in v["hits"] if h["tier"] == "M")
        w = sum(1 for h in v["hits"] if h["tier"] == "W")
        A(f"| {i} | {m.get('date','—')} | {m.get('regime','?')} | {m.get('dur_min',0)}min "
          f"| **{s}** | {mm} | {w} | {m.get('title','')[:40]} |")
    A("")
    A("## 五、逐期索引")
    A("")
    A("> 完整明细在 `_预筛地图.json`。这里只列 S 档 ≥2 的期次，")
    A("> 每条给出时间戳与命中词，供批读时定点查看。")
    A("")
    for eid, v in sorted(per_ep.items(), key=lambda x: -sum(1 for h in x[1]["hits"] if h["tier"] == "S")):
        s_hits = [h for h in v["hits"] if h["tier"] == "S"]
        if len(s_hits) < 2:
            continue
        m = meta.get(eid, {})
        A(f"### {m.get('title','')} ｜ {m.get('date','无日期')} ｜ {m.get('regime','?')} ｜ S×{len(s_hits)}")
        A("")
        A("| 时间 | 数字 | 触发 | 动作 | 摘录 |")
        A("|---|---|---|---|---|")
        for h in s_hits[:12]:
            txt = h["text"].replace("|", "｜")[:90]
            A(f"| {h['ts']} | {'、'.join(h['nums'][:4])} | {'、'.join(h['triggers'][:3])} "
              f"| {'、'.join(h['actions'][:3])} | {txt} |")
        A("")
    A("---")
    A("")
    A("> **合规**：本文件仅为研究学习其公开表达，不构成投资建议。**股市有风险，投资需谨慎。**")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"扫描 {len(per_ep)} 期 / {total_lines:,} 行")
    print(f"命中窗口 {total_hits:,}（S {tier_total['S']:,} / M {tier_total['M']:,} / W {tier_total['W']:,}）")
    print(f"有命中期数 {eps_with}/{len(per_ep)}")
    print(f"命中字数 {total_chars:,}（全量占比 {total_chars / 4915561 * 100:.1f}%）")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    print(f"→ {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
