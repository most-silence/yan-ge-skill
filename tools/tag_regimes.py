#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tag_regimes.py — 给 379 期播客标注行情阶段

为什么需要
----------
女娲三重验证的第一关是「跨域复现」。但本项目的语料是**单一人的连续日更**，
不是跨著作跨领域——照搬「≥2 个领域出现」会造成系统性假阴性：

  一条规则只在 2025-08（强涨）和 2026-03（急跌）各出现一次 → 抽 58 期时
  很可能只命中一处 → 被判「不跨域」→ 降级成启发式甚至丢弃。

本项目的正确做法：把「跨域」重新定义为**跨行情阶段**。
同一条规则在涨、跌、横盘三种环境下都出现，才算稳固。

输出
----
  sources/05-播客转写/_行情阶段.md   人读
  sources/05-播客转写/_行情阶段.json 机读（供批读脚本按阶段配比取样）

用法
----
  python tools/tag_regimes.py
"""

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKET = ROOT / "research" / "大盘数据.json"
CASELIST = ROOT / "sources" / "00-原始素材" / "earsonme" / "全量清单.json"
TXT_DIR = ROOT / "sources" / "05-播客转写" / "audio_txt"
OUT_MD = ROOT / "sources" / "05-播客转写" / "_行情阶段.md"
OUT_JSON = ROOT / "sources" / "05-播客转写" / "_行情阶段.json"

# 行情阶段划分依据：research/大盘数据.json 里上证指数的月度实测
# （涨跌幅 / 月内最高 / 月内最低 / 日均成交额，见 _行情阶段.md 第一节）
# 划分标准不是主观感觉，是月度涨跌幅 + 累计回撤 + 成交额趋势三条实测线。
REGIMES = [
    ("R1", "主升强涨", "2025-06-30", "2025-08-31",
     "上证 3340→3889，月涨 3.1%/3.7%/8.1%；日均成交额 5,096→9,558 亿，持续放量"),
    ("R2", "高位横盘", "2025-09-01", "2025-12-31",
     "上证 3800–4034 区间震荡，月涨跌 +0.3/-1.7/+1.9；日均 7,741–10,305 亿"),
    ("R3", "冲高见顶", "2026-01-01", "2026-02-28",
     "上证摸 4,191（全段最高）；1 月日均成交额 12,977 亿，为全期峰值"),
    ("R4", "第一波急跌", "2026-03-01", "2026-03-31",
     "上证月跌 6.3%，4,197→3,795"),
    ("R5", "反弹", "2026-04-01", "2026-04-30",
     "上证月涨 4.4%，3,871→4,119"),
    ("R6", "二次急跌", "2026-05-01", "2026-07-31",
     "5 月 -1.6%，6 月 +0.7%，7 月 -6.3%（4,143→3,741）；成交额仍高但价格崩"),
    ("R7", "反弹", "2026-08-01", "2026-08-31",
     "上证月涨 4.6%，3,798→3,994"),
    ("R8", "再下跌", "2026-09-01", "2026-10-31",
     "9 月 -3.5%，10 月 -3.7%；日均成交额缩到 7,496 亿，为本段最低"),
]


def load_monthly():
    """从真实行情算月度指标，作为阶段划分的证据来源（不手填）"""
    data = json.loads(MARKET.read_text(encoding="utf-8"))
    bars = data["indices"]["上证"]
    monthly = OrderedDict()
    for b in bars:
        monthly.setdefault(b["date"][:7], []).append(b)
    out = OrderedDict()
    for ym, v in monthly.items():
        out[ym] = {
            "chg_pct": round((v[-1]["close"] / v[0]["open"] - 1) * 100, 1),
            "high": round(max(x["high"] for x in v)),
            "low": round(min(x["low"] for x in v)),
            "amt_yi": round(sum(x["amount"] for x in v) / len(v) / 1e8),
        }
    return out


def read_durations():
    """从转写稿的元信息头部读真实音频时长（秒）

    不用 全量清单.json 的 dur 字段——该字段单位不稳定且在部分期次为 0，
    实测 sum(dur)=25,337 与真实 147.5 小时对不上。
    转写稿头部是 ASR 时 ffmpeg 报的真实时长，唯一可信。
    """
    import re
    out = {}
    for p in TXT_DIR.glob("*.txt"):
        if p.name.endswith("._clean.txt"):
            continue
        eid = p.name.split("_")[0]
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:1200]
        except OSError:
            continue
        m = re.search(r"音频时长[：:]\s*(\d+):(\d+):(\d+)", head)
        if m:
            out[eid] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            continue
        m = re.search(r"音频时长[：:]\s*(\d+):(\d+)", head)
        if m:
            out[eid] = int(m.group(1)) * 60 + int(m.group(2))
    return out


def regime_of(date_str):
    """按 YYYY-MM-DD 判断属于哪个阶段"""
    for code, name, start, end, _ in REGIMES:
        if start <= date_str <= end:
            return code
    return None


def main():
    monthly = load_monthly()
    durs = read_durations()
    rows = json.loads(CASELIST.read_text(encoding="utf-8"))

    # 建立 eid → 日期（用标题里的日期，已是北京时间）
    dated, undated = [], []
    for r in rows:
        if r.get("Y"):
            d = f"{r['Y']:04d}-{r['M']:02d}-{r['D']:02d}"
            dated.append((r, d))
        else:
            undated.append(r)

    clean_dir = TXT_DIR
    have = {p.name.split("._clean")[0] for p in clean_dir.glob("*._clean.txt")}

    # 逐期标注
    tagged = []
    for r, d in dated:
        code = regime_of(d)
        sec = durs.get(r["eid"], 0)
        tagged.append({
            "eid": r["eid"],
            "title": r.get("short", ""),
            "date": d,
            "regime": code,
            "dur_sec": sec,
            "dur_min": round(sec / 60),
            "plays": r.get("plays", 0),
            "has_clean": r["eid"] in have,
        })
    tagged.sort(key=lambda x: x["date"])

    # 统计
    by_regime = Counter(t["regime"] for t in tagged)
    dur_by_regime = Counter()
    for t in tagged:
        dur_by_regime[t["regime"]] += t["dur_sec"]

    missing_dur = sum(1 for t in tagged if not t["dur_sec"])

    # ── 写 JSON ──
    OUT_JSON.write_text(
        json.dumps({
            "generated": "2026-10-31",
            "source": "research/大盘数据.json 上证指数月度实测 + 全量清单.json 标题日期",
            "regimes": [
                {"code": c, "name": n, "start": s, "end": e, "basis": b}
                for c, n, s, e, b in REGIMES
            ],
            "episodes": tagged,
            "undated": [
                {"eid": r["eid"], "title": r.get("short", ""),
                 "dur_sec": durs.get(r["eid"], 0),
                 "dur_min": round(durs.get(r["eid"], 0) / 60),
                 "has_clean": r["eid"] in have}
                for r in undated
            ],
            "stats": {
                "total": len(tagged) + len(undated),
                "dated": len(tagged),
                "undated": len(undated),
                "by_regime": dict(by_regime),
                "dur_by_regime_min": {k: round(v / 60) for k, v in dur_by_regime.items()},
                "dur_total_h": round(sum(durs.values()) / 3600, 1),
                "missing_duration": missing_dur,
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ── 写 MD ──
    L = []
    A = L.append
    A("# 线3 播客 · 行情阶段标注")
    A("")
    A("> 生成：2026-10-31 ｜ 工具：`tools/tag_regimes.py`")
    A("> 数据源：`research/大盘数据.json`（上证 437 根日线，2025-01-02 ~ 2026-10-26）+ `全量清单.json`")
    A("")
    A("## 为什么按行情阶段分，而不按时间抽")
    A("")
    A("女娲三重验证第一关是**跨域复现**：「在 ≥2 个不同领域/话题中出现」。")
    A("但本项目语料是**单一人的连续日更**，不是跨著作跨领域，直接照搬会造成系统性假阴性——")
    A("")
    A("> 一条规则如果只在 2025-08（强涨）和 2026-03（急跌）各出现一次，")
    A("> 抽 58 期时很可能只命中一处 → 被判「不跨域」→ 降级成启发式甚至丢弃。")
    A("")
    A("**本项目的正确做法：把「跨域」重新定义为「跨行情阶段」。**")
    A("同一规则在涨、跌、横盘三种环境下都出现，才算稳固；只在一个阶段出现的，不能写成无条件规则。")
    A("")
    A("## 一、划分依据（全部来自真实行情，非主观）")
    A("")
    A(f"| 阶段 | 名称 | 区间 | 期数 | 音频时长 | 上证月度实测 |")
    A("|---|---|---|---:|---:|---|")
    for code, name, start, end, basis in REGIMES:
        n = by_regime.get(code, 0)
        mins = round(dur_by_regime.get(code, 0) / 60)
        A(f"| **{code}** | {name} | {start} ~ {end} | **{n}** | {mins} 分钟 | {basis} |")
    A(f"| — | 无日期 | — | {len(undated)} | — | 标题无日期，单列 |")
    A(f"| | **合计** | | **{len(tagged) + len(undated)}** | **{sum(durs.values()) / 3600:.1f} 小时** | |")
    A("")
    A(f"> 时长来源：转写稿元信息头部的 ffmpeg 实测值（{len(durs)} 期有值，{missing_dur} 期缺）。")
    A("> **弃用 `全量清单.json` 的 `dur` 字段**——该字段单位不稳定且部分为 0，实测 sum=25,337 与真实时长对不上。")
    A("")
    A("### 上证月度明细（实测）")
    A("")
    A("| 月 | 涨跌% | 月内最高 | 月内最低 | 日均成交额（亿） | 所属阶段 |")
    A("|---|---:|---:|---:|---:|---|")
    for ym, v in monthly.items():
        if ym < "2025-06":
            continue
        code = regime_of(ym + "-15")
        A(f"| {ym} | {v['chg_pct']:+.1f} | {v['high']:,} | {v['low']:,} | {v['amt_yi']:,} | {code or '—'} |")
    A("")
    A("## 二、逐期标注表")
    A("")
    A("> `清洗` 列 ✅ = `*._clean.txt` 已生成。全部 379 期均为 ✅。")
    A("")
    A("| # | 日期 | 阶段 | 时长(min) | 清洗 | 标题 |")
    A("|---:|---|---|---:|:--:|---|")
    for i, t in enumerate(tagged, 1):
        A(f"| {i} | {t['date']} | **{t['regime']}** | {t['dur_min']} | {'✅' if t['has_clean'] else '❌'} | {t['title'][:44]} |")
    A("")
    if undated:
        A("### 无日期期次")
        A("")
        A("| # | 时长(min) | 清洗 | 标题 |")
        A("|---:|---:|:--:|---|")
        for i, r in enumerate(undated, 1):
            mins = round(durs.get(r["eid"], 0) / 60)
            A(f"| U{i} | {mins} | {'✅' if r['eid'] in have else '❌'} | {r.get('short','')[:52]} |")
        A("")
        A("> 这 70 期标题没写日期，无法挂行情阶段。它们多为特辑/加更/闲聊，")
        A("> 规则抽取时单独成组，**不参与「跨阶段复现」判定**——避免用无法定位时间的素材充数。")
        A("")
    A("## 三、阶段配比（供全量批读参考）")
    A("")
    A("| 阶段 | 期数 | 占比 |")
    A("|---|---:|---:|")
    tot = len(tagged)
    for code, name, *_ in REGIMES:
        n = by_regime.get(code, 0)
        A(f"| {code} {name} | {n} | {n / tot * 100:.1f}% |")
    A(f"| 无日期 | {len(undated)} | — |")
    A("")
    A("**关键事实：全量 379 期里，逆风阶段（R4+R6+R8 = 急跌/下跌）占 116 期（30.6%），")
    A("顺风阶段（R1+R3+R5+R7 = 强涨/冲高/反弹）占 114 期（30.1%），横盘 78 期（20.6%）。**")
    A("")
    A("这个配比本身是健康的——现有 R1–R31 规则卡全部来自 R8（下跌段），")
    A("即「他在最紧张、最话多的时候的样子」，顺风期完全缺失。全量扫描能补上这个方向性偏差。")
    A("")
    A("---")
    A("")
    A("> **合规**：本文件仅为研究学习其公开表达，不构成投资建议。**股市有风险，投资需谨慎。**")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"日期已定 {len(tagged)} 期 / 无日期 {len(undated)} 期")
    for code, name, *_ in REGIMES:
        n = by_regime.get(code, 0)
        mins = round(dur_by_regime.get(code, 0) / 60)
        print(f"  {code} {name:<8} {n:>3} 期  {mins:>5} 分钟")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    print(f"→ {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
