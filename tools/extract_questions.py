#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""extract_questions.py — 从 test-prompts.md 抽出「只有题干」的清单

为什么要抽
----------
压力测试必须让答题者**看不到期望答案**，否则只是在复述我写的答案。
而期望答案本身可能是错的（这个项目已犯过 6 次），所以判定必须另起一轮、
对照原文做，不能拿 test-prompts.md 里的「期望表现」当真值。

输出
----
_stresstest/questions_<书>.md   只有编号 + 题干
_master.json                    全部题目的结构化清单
"""

import json
import re
import sys
from pathlib import Path

BOOKS = ["笑傲牛熊", "股票魔法师", "读财报", "股市操练大全4"]

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "books" / "04-技能"
OUT = ROOT / "_stresstest"


def parse_test_file(path: Path):
    """解析 test-prompts.md，返回 [(章节名, 编号, 题干)]

    表格行格式：| # | 问题 | 期望表现 | [风险列] |
    只取第 2 列作为题干。
    """
    rows = []
    section = "(未分节)"
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("## "):
            section = s[3:].strip()
            continue
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 3:
            continue
        num = cells[0]
        # 只认纯数字编号开头的行
        if not re.fullmatch(r"\d+", num):
            continue
        q = cells[1]
        # 去掉粗体标记，保留文字
        q = q.replace("**", "").strip()
        if not q:
            continue
        rows.append((section, num, q))
    return rows


def main():
    OUT.mkdir(exist_ok=True)
    master = {}

    for book in BOOKS:
        tp = SKILL_DIR / book / "test-prompts.md"
        if not tp.exists():
            print(f"! 缺文件: {tp}", file=sys.stderr)
            continue
        rows = parse_test_file(tp)
        master[book] = [
            {"section": sec, "num": num, "q": q} for sec, num, q in rows
        ]

        # 写「只有题干」的文件
        lines = [f"# {book} — 压力测试题（无期望答案）",
                 "",
                 f"共 {len(rows)} 题。**只回答题干，不要猜测出题人想要什么答案。**",
                 "不确定的地方就说不确定——说「书里没给」也算一种回答，"
                 "但必须有依据。",
                 ""]
        cur = None
        for sec, num, q in rows:
            if sec != cur:
                cur = sec
                lines.append(f"## {sec}")
                lines.append("")
            lines.append(f"{num}. {q}")
        (OUT / f"questions_{book}.md").write_text("\n".join(lines) + "\n",
                                                  encoding="utf-8")
        print(f"  {book}: {len(rows)} 题 → questions_{book}.md")

    (OUT / "questions_master.json").write_text(
        json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v) for v in master.values())
    print(f"\n合计 {total} 题，已写入 {OUT}")


if __name__ == "__main__":
    main()
