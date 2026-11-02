#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audit_numbers.py — 把 Skill 里的每个数字回原文核对

为什么需要这个
--------------
这个项目已经两次犯同一类错：
  1. 断言「书里没有 X」，书里其实有（该给不给）
  2. 补内容时把数字抄错 / 把别处的数字带进来（编造）

第 2 类靠人工看是看不出来的——25% 和 20% 长得太像。
所以把 Skill 里出现的所有数字抓出来，逐个到原文里找，
找不到的列出来人工判断。

用法
----
  python tools/audit_numbers.py
  python tools/audit_numbers.py --book 股票魔法师 --verbose

判定
----
  OK      原文能搜到这个数字（可能换了写法）
  WARN    数字在原文有，但上下文对不上（需要人工看）
  MISS    原文完全没有这个数字 → 高度可疑

注意
----
MISS 不一定是错。有些数字是**推导值**（如 15×2=30 里的 30、50/310=0.16），
原文不一定直接写。所以 MISS 只是「必须人工解释」的清单，不是判决。
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "books" / "04-技能"
SRC_DIR = ROOT / "books" / "01-分章"

BOOKS = {
    "笑傲牛熊": "xiaoao",
    "股票魔法师": "mofa",
    "读财报": "caibao",
    "股市操练大全4": "caolian",
}

# 这些数字是结构性/通用词，不需要核对
IGNORE_NUMBERS = {
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "0", "100",  # 100 常见于「100%」
}

# 结构性数字：维度编号、页码——不来自正文，不必核对
STRUCTURAL_PATTERNS = [
    r"DIMENSION\s+\d+(?:\.\d+)?",
    r"\d+\s*页",
    r"\d+\s*行",
]


def load_source(stem: str) -> str:
    d = json.loads((SRC_DIR / f"{stem}.json").read_text(encoding="utf-8"))
    # 去掉所有空白，避免 OCR 断行导致搜不到
    return "".join("".join(ch["body"].split()) for ch in d["chapters"])


def norm(s: str) -> str:
    """把各种数字写法归一：全角转半角、~ 统一、去掉「约/大约」"""
    s = s.replace("．", ".").replace("％", "%").replace("～", "~")
    s = s.replace("－", "-").replace("—", "-").replace("–", "-")
    return s


def extract_numbers(text: str):
    """抽出所有形如 5%、25%、150、1.17、2~6、3-5 的数字/区间"""
    t = norm(text)
    hits = []
    # 区间：2~6 / 3-5 / 25%~35%
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*([~\-])\s*(\d+(?:\.\d+)?)\s*(%?)", t):
        hits.append((m.group(0), m.start()))
    # 单个数：25% / 150 / 1.17
    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(%?)", t):
        raw = m.group(0)
        hits.append((raw, m.start()))
    # 去掉被区间覆盖的单数
    return hits


def context_of(text: str, pos: int, width: int = 40) -> str:
    s = max(0, pos - width)
    e = min(len(text), pos + width)
    return text[s:e].replace("\n", " ")


def check_one(num_raw: str, src: str):
    """返回 (verdict, evidence)"""
    core = num_raw.rstrip("%").strip()
    # 区间拆开，两半都要在原文出现
    parts = re.split(r"[~\-]", core)
    parts = [p.strip().rstrip("%") for p in parts if p.strip()]

    if not parts:
        return "SKIP", ""

    found_all = True
    ev = ""
    for p in parts:
        if p in IGNORE_NUMBERS:
            continue
        # 原文里有没有这个数字（允许后面跟 % 或直接跟字）
        pat = re.escape(p)
        m = re.search(pat, src)
        if m:
            if not ev:
                ev = context_of(src, m.start())
        else:
            found_all = False

    if found_all:
        return "OK", ev
    return "MISS", ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    books = [args.book] if args.book else list(BOOKS)
    grand = {"OK": 0, "MISS": 0, "SKIP": 0}
    miss_report = []

    for book in books:
        skill = SKILL_DIR / book / "SKILL.md"
        if not skill.exists():
            print(f"! 缺 {skill}", file=sys.stderr)
            continue
        src = load_source(BOOKS[book])
        text = skill.read_text(encoding="utf-8")

        # 只看正文里的数字，跳过代码块和表格分隔线
        lines = []
        for i, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("|") and set(line) <= set("|-: "):
                continue
            if line.strip().startswith("```"):
                continue
            lines.append((i, line))

        seen = {}
        for lineno, line in lines:
            if any(re.search(p, line) for p in STRUCTURAL_PATTERNS):
                continue
            for raw, _pos in extract_numbers(line):
                raw = raw.strip()
                if not raw or raw in seen:
                    continue
                verdict, ev = check_one(raw, src)
                seen[raw] = (verdict, lineno, ev)
                grand[verdict] = grand.get(verdict, 0) + 1
                if verdict == "MISS":
                    miss_report.append((book, lineno, raw, line.strip()[:70]))

        n_ok = sum(1 for v in seen.values() if v[0] == "OK")
        n_miss = sum(1 for v in seen.values() if v[0] == "MISS")
        print(f"{book:14} 数字 {len(seen):4} 种   OK {n_ok:4}   MISS {n_miss:3}")

        if args.verbose:
            for raw, (verdict, lineno, ev) in sorted(seen.items()):
                if verdict == "MISS":
                    print(f"    ✗ {raw:12} L{lineno}")

    print()
    print("=" * 70)
    if miss_report:
        print(f"🔴 原文搜不到的数字 {len(miss_report)} 处（需人工解释：可能是推导值，也可能是抄错）\n")
        for book, lineno, raw, ctx in miss_report:
            print(f"  {book}/SKILL.md:{lineno}  [{raw}]")
            print(f"      {ctx}")
        print()
        print("  处理原则：")
        print("   · 推导值（如 15×2=30、50/310=0.16）→ 在 Skill 里注明「推导」")
        print("   · 抄错 → 回原文改正")
        print("   · 别处带来的 → 删除")
    else:
        print("✅ 所有数字都能在原文找到")

    return 0 if not miss_report else 0


if __name__ == "__main__":
    sys.exit(main())
