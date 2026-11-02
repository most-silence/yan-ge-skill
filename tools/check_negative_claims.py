#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_negative_claims.py — Q10 阴性证据校验（自动化）

背景
----
这个项目里同一类错误犯了 4 次：

  1. 判「眼哥风控是黑洞」  → 跳过了最长的一份转写
  2. 判「眼哥不看基本面」  → 只检索术语，漏了口语表达
  3. 判「笑傲牛熊不给止损规则」→ 第 6 章有 186 处止损 + 七条规则
  4. 判「读财报披露期限非书中内容」→ 第 1 章原文就写了

共同点：都是「断言素材里没有 X」，而 X 其实有。
「他没讲过」是强断言，举证责任比「他讲过」更重，因为拿不出原文可引。

这个脚本做的事
--------------
扫描产物里的否定断言 → 提取被否定的对象 → 用四类词回原文检索 → 报冲突。

四类词（缺一类就会漏）：
  1. 术语      教科书写法        （估值、市盈率）
  2. 大白话    他实际怎么说      （值多少钱、贵不贵）
  3. 近义词    替代说法          （基本面、底细、调研）
  4. 场景词    描述场景必出现的词（算清楚、掏钱）

用法
----
  python check_negative_claims.py --skill-dir books/04-技能 --sources books/01-分章
  python check_negative_claims.py --skill-dir books/04-技能 --sources books/01-分章 --verbose

退出码
------
  0  未发现冲突
  1  发现疑似冲突（需要人工确认）
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 同义词表
# 每条：对象名 → dict(words=[检索词], must=精确匹配正则 或 None)
#
# 为什么要 must
# -------------
# 光看「止损」出现 348 次，不能反驳「本书没给止损**百分比**」——
# 书里有一堆止损规则，但确实没有一个统一百分比。
# must 用来把「概念存在」和「具体断言的那个东西存在」区分开。
#
# CONFLICT 的判定：
#   有 must  → must 命中才算 CONFLICT（否则最多 WARN）
#   无 must  → 同义词命中 ≥5 次算 CONFLICT
SYNONYMS = {
    # ---- 风控 / 止损 ----
    # 断言「没给统一百分比」：必须有「止损…X%」这种绑定出现才算冲突
    # 注意排除「止损，哪怕成功率不到50%」这类——百分比不是止损幅度
    "止损百分比": {
        "words": ["止损", "个点", "割肉", "认赔", "保护性"],
        "must": r"止损[^。；，,]{0,10}(?:设|定|放|为|是|在|幅度)?[^。；，,]{0,4}?\d+\s*[%％]",
    },
    # 断言「没给止损落位规则」：必须有具体价位锚点
    "止损位置": {
        "words": ["前期低点", "整数", "突破点下方", "均线下方", "支撑下方"],
        "must": r"(?:前期低点|整数[价位关口]|突破点下方)[^。；]{0,30}\d",
    },
    "止损": {
        "words": ["止损", "割肉", "认赔", "砍掉", "离场", "保护性"],
        "must": None,
    },

    # ---- 仓位 ----
    # 断言「没给仓位方法」：必须有比例或分批表述
    "仓位分配": {
        "words": ["仓位", "半仓", "全仓", "建仓"],
        "must": r"(?:\d+\s*[%％]\s*的?仓位|仓位[^。；]{0,12}\d+\s*[%％]|买入一半|剩余[^。；]{0,8}一半)",
    },
    "仓位": {"words": ["仓位", "半仓", "全仓", "建仓"], "must": None},
    "单只上限": {
        "words": ["单只", "每只", "上限", "占总"],
        "must": r"(?:单只|每只)[^。；]{0,20}\d+\s*[%％]",
    },

    # ---- 均线 ----
    # 断言「没给具体均线」：必须有「N日/N周+均线」
    "均线参数": {
        "words": ["均线", "日线", "周线", "移动平均"],
        "must": r"\d+\s*(?:日|周|天)\s*(?:均线|移动平均|平均线)",
    },
    "均线": {"words": ["均线", "日线", "周线", "移动平均"], "must": None},

    # ---- 四阶段 ----
    "四阶段": {
        "words": ["四阶段", "阶段"],
        "must": r"(?:四阶段|第一阶段|第二阶段|第三阶段|第四阶段)",
    },
    "阶段判定": {"words": ["阶段", "巩固", "突围", "到顶", "衰败"], "must": None},

    # ---- 估值 ----
    # 断言「不做估值」：需要出现估值方法论词
    "估值方法": {
        "words": ["估值", "市盈率", "P/E", "折现", "清算价值"],
        "must": r"(?:现金流折现|清算价值|DCF|估值模型|内在价值)",
    },
    "估值": {"words": ["估值", "市盈率", "值多少钱", "贵不贵"], "must": None},

    # ---- 基本面 ----
    "基本面": {
        "words": ["基本面", "底细", "调研", "利润", "营收", "盈利", "业绩"],
        "must": None,
    },
    "财报": {"words": ["财报", "报表", "年报", "季报", "三张表"], "must": None},

    # ---- 披露 ----
    "披露期限": {
        "words": ["披露", "按规定"],
        "must": r"\d+\s*个月内[^。；]{0,10}披露",
    },

    # ---- 量能 / 止盈 ----
    "放量": {"words": ["放量", "成交量", "量能", "天量"], "must": None},
    # 断言「没给放量倍数」：需要「放量N倍」
    "放量倍数": {
        "words": ["放量", "成交量"],
        "must": r"(?:放量|成交量)[^。；]{0,16}\d+\s*倍",
    },
    "止盈": {"words": ["止盈", "落袋", "获利了结"], "must": None},

    # ---- 选股 / 买卖点 ----
    "选股": {"words": ["选股", "怎么选", "找股票", "标的"], "must": None},
    "买点": {"words": ["买点", "买入时机", "进场", "突破点", "回调点"], "must": None},
    "卖点": {"words": ["卖点", "卖出时机", "离场"], "must": None},

    # ---- 形态 ----
    "基底": {"words": ["基底", "整理", "盘整", "横盘", "筑底"], "must": None},
    "杯柄": {"words": ["杯柄", "杯状", "带柄"], "must": None},
    "VCP": {"words": ["VCP", "波动收窄", "收缩"], "must": None},

    # ---- 相对强度 ----
    # 断言「没给 RS 公式」：需要公式/计算式
    "相对强度公式": {
        "words": ["相对强度", "RPS", "RS"],
        "must": r"(?:相对强度|RPS)[^。；]{0,40}(?:[=＝]|除以|比值|计算[方式法])",
    },
    "相对强度": {"words": ["相对强度", "RPS", "相对强弱"], "must": None},

    # ---- 杠杆 ----
    "杠杆": {"words": ["杠杆", "融资", "配资"], "must": None},

    # ---- 大盘 / 宏观 ----
    "大盘": {"words": ["大盘", "指数", "市场整体", "牛熊"], "must": None},
    "宏观": {"words": ["宏观", "利率", "经济周期"], "must": None},

    # ---- 心理 ----
    "心理": {"words": ["心理", "情绪", "恐惧", "贪婪", "耐心", "纪律"], "must": None},

    # ---- 摊低成本 ----
    "摊低成本": {
        "words": ["摊低成本", "摊薄", "补仓", "越跌越买"],
        "must": None,
    },

    # ---- 财报科目 ----
    # 断言「没给阈值」：需要科目+数字%
    "毛利率阈值": {
        "words": ["毛利率", "净利率"],
        "must": r"(?:毛利率|净利率)[^。；]{0,20}\d+\s*[%％]",
    },
    "毛利率": {"words": ["毛利率", "净利率", "税收", "费用率"], "must": None},
    "商誉阈值": {
        "words": ["商誉", "无形资产"],
        "must": r"商誉[^。；]{0,20}\d+\s*[%％]",
    },
    "商誉": {"words": ["商誉", "无形资产", "减值"], "must": None},
    "现金流": {"words": ["现金流", "经营活动"], "must": None},
    "应收账款": {"words": ["应收账款", "应收", "账龄"], "must": None},

    # ---- 时代性 ----
    "时代": {"words": ["1980", "1990", "2000", "那个年代"], "must": None},
}

# ---------------------------------------------------------------- 否定断言模式
# 只抓「断言素材缺失」的句式，不抓「这个 Skill 不展开」这类正当边界声明
NEGATIVE_PATTERNS = [
    # 强否定
    (r"(?:本书|书里|书中|笔记里|原文|全书)(?:并)?(?:没|没有|未|不曾)(?:给|讲|提|涉及|展开|讨论|定义|说明)(?:过)?[^。\n，,]{1,20}", "本书没给"),
    # 零提及类
    (r"(?:零提及|完全未提及|从未提及|0\s*次|零次)", "零提及"),
    # 展开类
    (r"(?:没有|未)(?:展开|细化|量化|给(?:出)?(?:具体|阈值|公式|数字))[^。\n，,]{0,16}", "未展开"),
    # 不属于范围
    (r"(?:本书|书里)(?:不|没有)(?:涉及|覆盖|讨论)", "未涉及"),
]

# 这些是**正当的**边界声明，不算「否定断言」，跳过
WHITELIST = [
    r"本\s*Skill\s*(?:不|没有)",
    r"本章不展开",
    r"不在本书范围",
    r"原书第\s*\d+\s*章.*本\s*Skill\s*不",
    # 引号内的「不要说 X」= 纠正说明，本身就是在否定这个错误说法
    r"不(?:要|能|许)说[「『\"].{0,30}(?:没|不)",
    r"不(?:要|能|许)再(?:说|认为)",
]

# 疑似阈值词（出现这些说明在讨论「多少算异常」）
THRESHOLD_WORDS = ["阈值", "多少算", "幅度", "倍数", "比例", "百分比", "上限"]

# 反驳词：must 命中的上下文里出现这些，说明**书在否定这个做法**，
# 那么「本书不给 X」的断言其实成立。（例：温斯坦说「一律设 10%~15% 止损」
# 是错误建议——所以「本书不给统一百分比」是对的，不是漏查。）
REFUTE_WORDS = ["错误", "不对", "不应该", "并非", "而不是", "要不得",
                "坏名声", "误", "不可取", "无稽"]


def load_sources(src_dir: Path) -> dict:
    """载入所有分章 JSON，返回 {书名: 全文去空白}"""
    out = {}
    for p in sorted(src_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! 跳过 {p.name}: {e}", file=sys.stderr)
            continue
        text = "".join("".join(c.get("body", "").split()) for c in d.get("chapters", []))
        out[p.stem] = text
    return out


def find_negative_claims(md_path: Path):
    """找出文件里所有否定断言，返回 [(行号, 原句, 类型)]"""
    claims = []
    lines = md_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines, 1):
        # 跳过白名单
        if any(re.search(w, line) for w in WHITELIST):
            continue
        for pat, kind in NEGATIVE_PATTERNS:
            for m in re.finditer(pat, line):
                claims.append((i, m.group(0).strip(), kind))
    return claims


def match_object(claim_text: str):
    """从否定断言里找出被否定的对象，返回 (对象名, 配置) 或 None。
    长名优先：『止损百分比』优先于『止损』。"""
    for obj in sorted(SYNONYMS, key=len, reverse=True):
        cfg = SYNONYMS[obj]
        if obj in claim_text:
            return obj, cfg
        for w in cfg["words"]:
            if len(w) >= 2 and w in claim_text:
                return obj, cfg
    return None


def check_file(md_path: Path, book_stem: str, sources: dict, verbose=False):
    """检查一个 md 文件。

    判定：
      有 must -> must 命中 = CONFLICT；只 words 命中 = WARN；都没 = OK
      无 must -> words 命中 >=5 = CONFLICT；1~4 = WARN；0 = OK
    """
    if book_stem not in sources:
        return []
    text = sources[book_stem]
    results = []

    for lineno, claim, kind in find_negative_claims(md_path):
        hit = match_object(claim)
        if not hit:
            if verbose:
                results.append({"file": md_path.name, "line": lineno, "claim": claim,
                                "kind": kind, "object": "(未识别)", "verdict": "SKIP",
                                "evidence": "", "counts": {}})
            continue

        obj, cfg = hit
        words, must = cfg["words"], cfg["must"]

        counts = {}
        for w in words:
            c = text.count(w)
            if c:
                counts[w] = c
        total = sum(counts.values())

        must_hit = False
        must_sample = ""
        refuted = False
        if must:
            m = re.search(must, text)
            if m:
                must_hit = True
                s = max(0, m.start() - 30)
                must_sample = text[s:m.end() + 40]
                # 判断书是不是在「反驳」这个做法
                win_s = max(0, m.start() - 80)
                win_e = min(len(text), m.end() + 120)
                window = text[win_s:win_e]
                refuted = any(rw in window for rw in REFUTE_WORDS)

        if must:
            if must_hit and refuted:
                # 命中，但书在否定它 → 断言「本书不给」成立
                verdict = "OK"
            elif must_hit:
                verdict = "CONFLICT"
            elif total >= 5:
                verdict = "WARN"
            else:
                verdict = "OK"
        else:
            verdict = "CONFLICT" if total >= 5 else ("WARN" if total > 0 else "OK")

        ev = " ".join(f"{w}x{c}" for w, c in sorted(counts.items(), key=lambda x: -x[1])[:6])
        if must_sample:
            ev += "  || 精确命中: " + must_sample
            if refuted:
                ev += "  [书在反驳此做法→断言成立]"

        results.append({"file": md_path.name, "line": lineno, "claim": claim,
                        "kind": kind, "object": obj, "verdict": verdict,
                        "evidence": ev, "counts": counts})
    return results



def main():
    ap = argparse.ArgumentParser(description="Q10 阴性证据校验")
    ap.add_argument("--skill-dir", required=True, help="Skill 产物目录（含各书子目录）")
    ap.add_argument("--sources", required=True, help="分章 JSON 目录")
    ap.add_argument("--verbose", action="store_true", help="显示未识别的断言")
    ap.add_argument("--only", help="只检查某本书（目录名）")
    args = ap.parse_args()

    skill_dir = Path(args.skill_dir)
    src_dir = Path(args.sources)
    if not skill_dir.is_dir():
        sys.exit(f"目录不存在: {skill_dir}")
    if not src_dir.is_dir():
        sys.exit(f"目录不存在: {src_dir}")

    sources = load_sources(src_dir)
    if not sources:
        sys.exit("没有载入任何素材")

    print(f"载入素材: {', '.join(f'{k}({len(v)}字)' for k, v in sources.items())}")
    print("=" * 78)

    # 书目录名 → 素材 stem 的映射（目录名是中文，stem 是拼音）
    name_map = {
        "笑傲牛熊": "xiaoao",
        "股票魔法师": "mofa",
        "读财报": "caibao",
        "股市操练大全4": "caolian",
    }

    all_results = []
    for book_dir in sorted(skill_dir.iterdir()):
        if not book_dir.is_dir():
            continue
        if args.only and book_dir.name != args.only:
            continue
        stem = name_map.get(book_dir.name)
        if not stem:
            continue
        for md in sorted(book_dir.rglob("*.md")):
            res = check_file(md, stem, sources, args.verbose)
            for r in res:
                r["book"] = book_dir.name
            all_results.extend(res)

    # 按判定分组输出
    conflicts = [r for r in all_results if r["verdict"] == "CONFLICT"]
    warns = [r for r in all_results if r["verdict"] == "WARN"]
    oks = [r for r in all_results if r["verdict"] == "OK"]

    if conflicts:
        print(f"\n🔴 CONFLICT — 断言「没有」，但原文命中很多（{len(conflicts)} 处）\n")
        for r in conflicts:
            print(f"  {r['book']}/{r['file']}:{r['line']}")
            print(f"    断言: {r['claim'][:70]}")
            print(f"    对象: {r['object']}")
            print(f"    原文: {r['evidence']}")
            print()

    if warns:
        print(f"\n🟡 WARN — 有命中但不多，需人工确认（{len(warns)} 处）\n")
        for r in warns:
            print(f"  {r['book']}/{r['file']}:{r['line']}  [{r['object']}] {r['claim'][:56]}")
            print(f"     原文: {r['evidence']}")

    print(f"\n{'=' * 78}")
    print(f"✅ OK（断言成立）      : {len(oks)} 处")
    print(f"🟡 WARN（待人工确认）  : {len(warns)} 处")
    print(f"🔴 CONFLICT（很可能错）: {len(conflicts)} 处")
    print(f"   合计                : {len(all_results)} 处")

    if conflicts:
        print("\n提示：CONFLICT 不一定都是错——有些是「书里有这个概念，但确实没给具体阈值」。")
        print("     逐条看原文，确认是「有/无」，再改产物。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
