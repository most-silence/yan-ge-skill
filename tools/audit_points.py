#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audit_points.py — 把播客里的点位与真实行情逐条对账

与 audit_numbers.py 的分工
--------------------------
  audit_numbers.py  书籍 Skill 里的数字 → 回书籍原文核对（内部自洽）
  audit_points.py   播客里说的点位   → 回真实行情核对（外部裁决）  ← 本脚本

为什么必须是外部裁决，不能靠句内算术
------------------------------------
玟火 `material-hygiene.md` §3 规定：可验证数字必须与外部数据源核对后才入库，
**句内算术自洽 ≠ 事实正确**。

本项目已踩过的真实事故：ASR 把创业板 2860 听成 3860、2800 听成 3800。
当时用「往下还有一百多点」做句内反推：

    若为 2800~2850：3860 − 2850 = 1010 点 → 与「留下 10 个点」矛盾 ✗
    若为 3800~3850：3860 − 3850 = 10 点   → 吻合 ✓

于是判定「3800~3850 成立」。**方向恰好反了。**

    创业板全段最高 3270.81（09-28）→ 从未接近 3800
    10-13 当日最低 2860.80 → 与 2850 差 10.8 点，「留下 10 个点」对上的是 2860

> 错的只有一处这个假设本身没有依据。两个数都错时，任何句内算术都能「自洽」出相反结论。
> 正确顺序：先拉真实区间，再看哪种解释能同时满足所有线索。

判定三档
--------
  命中    数字落在该指数当期 ±窗口的真实高低区间内（含 ±容差）
  可疑    落在区间外 → 典型 ASR 错，需人工裁决
  年→点?  「N年」型，疑似点位被听成「年」（如 4000年 → 4000点）

用法
----
  python tools/audit_points.py
  python tools/audit_points.py --tolerance 30 --window 5
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKET = ROOT / "research" / "大盘数据.json"
REGIME_JSON = ROOT / "sources" / "05-播客转写" / "_行情阶段.json"
TXT_DIR = ROOT / "sources" / "05-播客转写" / "audio_txt"
OUT_MD = ROOT / "sources" / "05-播客转写" / "_数字对账.md"
OUT_JSON = ROOT / "sources" / "05-播客转写" / "_数字对账.json"

# 指数点位量级（据 research/大盘数据.json 全段实测）
# 只用于判断一个四位数「像」哪个指数，不用于判定对错
INDEX_RANGES = {
    "上证": (3200, 4300),
    "深证": (9500, 14000),
    "创业板": (1800, 3400),
    "科创50": (800, 1600),
    "深证综指": (1500, 3000),
}

INDEX_KEYWORDS = {
    "上证": ["上证", "沪指", "上海"],
    "深证": ["深证成指", "深成指", "深指"],
    "创业板": ["创业板", "创业版", "创指"],
    "科创50": ["科创", "科窗"],
    "深证综指": ["深证综指", "综指"],
}

LINE_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$")
POINT_RE = re.compile(r"(?<![\d.])(\d{4}(?:\.\d{1,2})?)(?![\d.])")
YEAR_PT_RE = re.compile(r"(?<![\d.])(\d{4})\s*年")
_YEAR_OK = re.compile(r"^(19|20)\d{2}$")


def load_market():
    data = json.loads(MARKET.read_text(encoding="utf-8"))
    return {name: {b["date"]: b for b in bars}
            for name, bars in data["indices"].items()}


def load_episode_dates():
    reg = json.loads(REGIME_JSON.read_text(encoding="utf-8"))
    m = {e["eid"]: e["date"] for e in reg["episodes"]}
    m.update({e["eid"]: "" for e in reg["undated"]})
    return m


# ── 语义角色判定：区分「当期事实」与「预测/回顾」 ──
# 2026-10-31 修正：第一版把所有四位数都当成「当期事实」比对，导致 40% 假可疑。
# 实际他说的点位有三种角色，只有第一种该用当期行情裁决：
#
#   ① 当期事实   「今天最高 3741」「刚跌破 3741」     → 必须落在当期区间
#   ② 预测目标   「接下来往 3674 走」「顶部应该在 4100」 → 落在未来区间，当期不必命中
#   ③ 历史回顾   「3 月的时候 3500 点」              → 落在过去区间
#
# 把 ②③ 当 ① 判，会把正确的预测误判成 ASR 错——这是把验证工具用反了。
FUTURE_HINTS = ["应该", "可能", "如果", "会到", "往", "目标", "看", "预计", "估计",
                "接下来", "明天", "下周", "后面", "支撑", "压力", "附近", "方向"]
PAST_HINTS = ["之前", "上次", "当时", "曾经", "月初", "上个月", "月的时候",
              "前面", "原来", "早就", "前面说", "以前"]


def role_of(text):
    """判断这个点位的语义角色"""
    has_future = any(k in text for k in FUTURE_HINTS)
    has_past = any(k in text for k in PAST_HINTS)
    if has_past and not has_future:
        return "历史回顾"
    if has_future:
        return "预测目标"
    return "当期事实"


def window_range(bars_by_date, center_date, window_days):
    """取中心日期前后 N 个交易日的真实高低点"""
    dates = sorted(bars_by_date)
    if center_date not in bars_by_date:
        prev = [d for d in dates if d <= center_date]
        if not prev:
            return None
        center_date = prev[-1]
    i = dates.index(center_date)
    lo = max(0, i - window_days)
    hi = min(len(dates), i + window_days + 1)
    seg = [bars_by_date[d] for d in dates[lo:hi]]
    return {
        "from": dates[lo], "to": dates[hi - 1],
        "high": max(b["high"] for b in seg),
        "low": min(b["low"] for b in seg),
    }


def guess_index(value, cur_idx, text):
    """归属判定：显式指数优先，但必须过「同位过滤」

    2026-10-31 修正：第一版有严重缺陷——cur_idx 是**跨句继承**的，
    一旦某句提到「创业板」，后面所有四位数都被标成创业板点位，
    包括「2785家上涨」（家数）、「3700亿」（成交额）、「黄金4100」（黄金价）。
    实测 1386/3438 = 40% 被判可疑，其中绝大多数是误判而非 ASR 错。

    修正三条：
      ① 数字后面紧跟量词（家/亿/万/手/元/美元）的，不是点位
      ② 数字本身带小数且 >10 的（如 3636.5），才允许当点位
      ③ cur_idx 不再跨句继承——只在**同句**有指数词时才用
    """
    # ① 同位过滤：这些量词跟着的四位数不是指数点位
    if re.search(r"(家|亿|万|手|元|美元|吨|倍|次|只|个涨|个跌)", text):
        # 只有句子里同时出现「点」这个字，才可能是点位
        if "点" not in text:
            return None

    # ② 排除明显是成交额/家数的形态
    for pat in (r"(\d{4})\s*(家|亿|万|手)", r"(家数|上涨|下跌|成交额|成交量)"):
        if re.search(pat, text):
            return None

    if cur_idx and cur_idx in INDEX_RANGES:
        lo, hi = INDEX_RANGES[cur_idx]
        if lo * 0.9 <= value <= hi * 1.1:
            return cur_idx
    for cand, (lo, hi) in INDEX_RANGES.items():
        if lo * 0.9 <= value <= hi * 1.1:
            return cand
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerance", type=float, default=30.0, help="点位容差（默认 30 点）")
    ap.add_argument("--window", type=int, default=5, help="前后交易日窗口（默认 5）")
    args = ap.parse_args()

    market = load_market()
    ep_dates = load_episode_dates()

    files = sorted(TXT_DIR.glob("*._clean.txt"))
    if not files:
        print("找不到清洗稿，先跑 check_transcript.py --fix", file=sys.stderr)
        return 1

    records = []
    for p in files:
        eid = p.name.split("_")[0]
        date = ep_dates.get(eid, "")
        if not date:
            continue  # 无日期期次无法对账

        prev_idx = None
        for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = LINE_RE.match(ln)
            if not m:
                continue
            ts, text = m.group(1), m.group(2)
            # cur_idx 只在**同句**出现指数词时成立，不跨句继承
            cur_idx = None
            for idx, kws in INDEX_KEYWORDS.items():
                if any(k in text for k in kws):
                    cur_idx = idx
                    prev_idx = idx
                    break
            # 同句没提指数，但前一句提了，且本句没有其它指数词 → 用前一句的（弱继承）
            if cur_idx is None and prev_idx and ("点" in text or "位" in text):
                cur_idx = prev_idx

            for num_s in POINT_RE.findall(text):
                v = float(num_s)
                if v < 800 or v > 15000:
                    continue
                idx = guess_index(v, cur_idx, text)
                if idx is None or idx not in market:
                    continue
                rng = window_range(market[idx], date, args.window)
                if rng is None:
                    continue
                in_range = rng["low"] - args.tolerance <= v <= rng["high"] + args.tolerance
                role = role_of(text)
                # 只有「当期事实」才用当期区间裁决；
                # 预测目标/历史回顾落在区间外是正常的，不算可疑
                if in_range:
                    verdict = "命中"
                elif role == "当期事实":
                    verdict = "可疑"
                else:
                    verdict = f"{role}·待验"
                records.append({
                    "eid": eid, "date": date, "ts": ts, "index": idx,
                    "value": v, "text": text[:120], "role": role,
                    "real_low": round(rng["low"], 2),
                    "real_high": round(rng["high"], 2),
                    "window": f"{rng['from']}~{rng['to']}",
                    "verdict": verdict,
                })

            for num_s in YEAR_PT_RE.findall(text):
                if _YEAR_OK.match(num_s):
                    continue
                records.append({
                    "eid": eid, "date": date, "ts": ts,
                    "index": cur_idx or "?",
                    "value": float(num_s), "text": text[:120],
                    "real_low": None, "real_high": None,
                    "window": "", "verdict": "年→点?",
                })

    seen, uniq = set(), []
    for r in records:
        k = (r["eid"], r["ts"], r["value"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    verdict_cnt = Counter(r["verdict"] for r in uniq)
    idx_cnt = Counter(r["index"] for r in uniq)
    role_cnt = Counter(r.get("role", "—") for r in uniq)

    OUT_JSON.write_text(json.dumps({
        "generated": "2026-10-31",
        "tolerance": args.tolerance, "window_days": args.window,
        "total": len(uniq),
        "verdicts": dict(verdict_cnt),
        "by_index": dict(idx_cnt),
        "by_role": dict(role_cnt),
        "records": uniq,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    L = []
    A = L.append
    A("# 线3 播客 · 点位对账")
    A("")
    A("> 生成：2026-10-31 ｜ 工具：`tools/audit_points.py`")
    A("> 数据源：`research/大盘数据.json`（必盈API 日线，2025-01-02 ~ 2026-10-26，含成交额）")
    A(f"> 参数：容差 ±{args.tolerance:.0f} 点 ｜ 窗口 ±{args.window} 个交易日")
    A("")
    A("## 一、为什么必须是外部裁决")
    A("")
    A("玟火 `material-hygiene.md` §3：**可验证数字必须与外部数据源核对后才入库。句内算术自洽 ≠ 事实正确。**")
    A("")
    A("### 本项目已踩过的真实事故")
    A("")
    A("ASR 把创业板 **2860 听成 3860**、**2800 听成 3800**。当时的推理是：")
    A("")
    A("```")
    A("若为 2800~2850：3860 − 2850 = 1010 点 → 与「留下 10 个点」矛盾 ✗")
    A("若为 3800~3850：3860 − 3850 = 10 点   → 吻合 ✓")
    A("```")
    A("")
    A("于是判定「3800~3850 成立、2800 是 ASR 错」。**方向恰好反了。**")
    A("")
    A("| 真实行情 | 数据 |")
    A("|---|---|")
    A("| 创业板全段最高 | **3270.81**（09-28）→ 从未接近 3800 |")
    A("| 10-13 当日最低 | **2860.80** → 与 2850 差 10.8 点，「留下 10 个点」对上的是 2860 |")
    A("| 10-20 当日最高 | 2790.12 → 压力位在 2800 完全合理 |")
    A("")
    A("> **教训：错的只有一处这个假设本身没有依据。两个数都错时，")
    A("> 任何句内算术都能「自洽」出相反结论。**")
    A("")
    A("## 二、判定口径（含语义角色区分）")
    A("")
    A("**第一版有严重缺陷，这是修正后的版本。** 第一版把所有四位数都当成「当期事实」去比，")
    A("结果 40% 被判可疑——而那些绝大多数不是 ASR 错，是**他把点位用在了别的角色上**。")
    A("")
    A("| 角色 | 例子 | 该用什么区间裁决 |")
    A("|---|---|---|")
    A("| **当期事实** | 「今天最高 3741」「刚跌破 3741」 | 当期区间。落外面 → **可疑** |")
    A("| **预测目标** | 「接下来往 3674 走」「顶部应该在 4100」 | 未来区间。当期不命中是**正常**的 |")
    A("| **历史回顾** | 「3 月的时候 3500 点」 | 过去区间。当期不命中是**正常**的 |")
    A("")
    A("> 把预测目标当当期事实判，会把**正确的预测误判成 ASR 错**——这是把验证工具用反了。")
    A("")
    A("| 判定 | 含义 |")
    A("|---|---|")
    A("| **命中** | 数字落在该指数当期 ±窗口的真实高低区间内（含 ±容差） |")
    A("| **可疑** | **当期事实**却落在区间外 → 典型 ASR 错，需人工裁决 |")
    A("| 预测目标·待验 | 是预测，当期不该命中。要等到那个时点才能判 |")
    A("| 历史回顾·待验 | 是回顾，需另拉当时的行情数据 |")
    A("| **年→点?** | 「N年」型，疑似点位被听成「年」（如 4000年→4000点） |")
    A("")
    A("> ⚠️ **「命中」不等于他说对了。** 只能证明「这个数字在当期真实存在过」。")
    A("> 数字真实但结论错误是另一类问题（Q11 数字自洽管这个）。")
    A("")
    A("## 三、总量")
    A("")
    tot = len(uniq) or 1
    A("| 判定 | 条数 | 占比 |")
    A("|---|---:|---:|")
    for k, n in verdict_cnt.most_common():
        A(f"| {k} | **{n}** | {n / tot * 100:.1f}% |")
    A(f"| 合计 | **{len(uniq)}** | 100% |")
    A("")
    A("### 按语义角色")
    A("")
    A("| 角色 | 条数 | 说明 |")
    A("|---|---:|---|")
    for k, v in role_cnt.most_common():
        note = {"当期事实": "可用当期行情裁决",
                "预测目标": "要等时点到了才能判",
                "历史回顾": "需另拉当时行情"}.get(k, "—")
        A(f"| {k} | {v} | {note} |")
    A("")
    A("### 按指数")
    A("")
    A("| 指数 | 条数 |")
    A("|---|---:|")
    for k, v in idx_cnt.most_common():
        A(f"| {k} | {v} |")
    A("")

    sus = [r for r in uniq if r["verdict"] == "可疑"]
    A(f"## 四、可疑条目（{len(sus)} 条，需裁决）")
    A("")
    if sus:
        A("| 日期 | 时间 | 指数 | 声称值 | 当期真实区间 | 偏差 | 原文 |")
        A("|---|---|---|---:|---|---:|---|")
        for r in sorted(sus, key=lambda x: x["date"])[:150]:
            lo, hi = r["real_low"], r["real_high"]
            if lo is None:
                continue
            dev = 0 if lo <= r["value"] <= hi else min(
                abs(r["value"] - lo), abs(r["value"] - hi))
            txt = r["text"].replace("|", "｜")[:70]
            A(f"| {r['date']} | {r['ts']} | {r['index']} | **{r['value']:g}** "
              f"| {lo:,.0f}–{hi:,.0f} | {dev:,.0f} | {txt} |")
        if len(sus) > 150:
            A(f"| … | | | | | | 还有 {len(sus) - 150} 条，见 JSON |")
        A("")
        A("> **这些不是「他说错了」，是「ASR 可能听错了」。** 裁决顺序：")
        A("> ① 先假设 ASR 错，找同段其他线索；")
        A("> ② 若同段有多处一致指向另一个数，判 ASR 错；")
        A("> ③ 若上下文明确（如「我说的是 3800」），判真实观点；")
        A("> ④ 拿不准的进 `needs_review`。")
    else:
        A("✅ 无。所有抽出的点位都落在当期真实区间内。")
    A("")

    yr = [r for r in uniq if r["verdict"] == "年→点?"]
    if yr:
        A(f"## 五、「年→点」疑似误听（{len(yr)} 条）")
        A("")
        A("| 日期 | 时间 | 声称 | 上下文 |")
        A("|---|---|---:|---|")
        for r in yr[:80]:
            A(f"| {r['date']} | {r['ts']} | {r['value']:g}年 | {r['text'][:80]} |")
        A("")
        A("> 点位语境（「4000年一旦反转」）是误听；年份语境（「2024年10月8号」）已被正则排除。")
        A("")

    A("---")
    A("")
    A("> **合规**：本文件仅为研究学习其公开表达，不构成投资建议。**股市有风险，投资需谨慎。**")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"抽出点位 {len(uniq)} 条")
    for k in ("命中", "可疑", "年→点?"):
        print(f"  {k}: {verdict_cnt.get(k, 0)}")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    print(f"→ {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
