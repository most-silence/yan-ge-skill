#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fill_test_results.py — 把四本 test-prompts.md 的自测结果表换成实跑数据

实跑数据来自 _stresstest/压力测试实跑记录.md（第三轮）。
注意：不再按类别拆「通过数」——第三轮判卷是按题给判定，
按类别汇总会失真（同一类里有的过有的不过）。所以给总数 + 未过清单。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SK = ROOT / "books" / "04-技能"

# 书: (总题数, 通过, 不精确, 该给不给, 未过题号说明)
DATA = {
    "笑傲牛熊": (26, 25, 1, 0,
             "#24 「回调到突破点多小算幅度小」——书里用 4%~6% 描述大牛股的回调深度，"
             "本 Skill 把它降格成「止损落位算例」，说「不是幅度相关的数字」过头了"),
    "股票魔法师": (36, 33, 2, 1,
              "#12 「第 8 章」——判为缺失，但第 8 章内容在（笔记编号错位成「第 9 章」），"
              "真正缺的是第 1 章；#21 150 日 vs 30 周的表述已在第三轮改正，"
              "但历史答案仍按旧说法；#26 「不要分散」在书里有立场"),
    "读财报": (35, 34, 1, 0,
             "#6 「四个维度」里的三项费用率取自第 3 章，不在第 1 章那句引文范围内"),
    "股市操练大全4": (34, 30, 1, 3,
                "#20 反技术与均线的组合规则（提醒之 005 分层）已补，"
                "但答案仍按旧版答；#23 长虹案例已补进 Overview；"
                "#28 题材 vs 理念已补见 DIMENSION 3.5"),
}

HEAD_RE = re.compile(r"^## .*自测结果.*$", re.M)


def main():
    for book, (total, ok, warn, missing, note) in DATA.items():
        p = SK / book / "test-prompts.md"
        t = p.read_text(encoding="utf-8")

        new_block = f"""## 自测结果（第三轮实跑）

> 实跑方式：答题 agent **只准读 SKILL.md**，禁止看本文件；
> 判卷 agent **对着原书全文判**，不采信本文件里的「期望表现」。
> 完整三轮记录见 `_stresstest/压力测试实跑记录.md`。

| 项 | 数 |
|---|---:|
| 题目总数 | **{total}** |
| 通过 | **{ok}** |
| 不精确（方向对、漏条件） | {warn} |
| 该给不给（原书有、Skill 说没有） | {missing} |

**未过的题**：{note}

---

"""

        # 找到「自测结果」标题，替换到下一个 `---` 之前
        m = HEAD_RE.search(t)
        if not m:
            print(f"  ✗ {book} 找不到自测结果标题")
            continue
        start = m.start()
        after = t[m.end():]
        # 下一个 --- 分隔
        sep = after.find("\n---\n", 10)
        if sep == -1:
            print(f"  ✗ {book} 找不到结束分隔")
            continue
        end = m.end() + sep + len("\n---\n")
        t = t[:start] + new_block + t[end:]
        p.write_text(t, encoding="utf-8")
        print(f"  ✓ {book}: {ok}/{total}")


if __name__ == "__main__":
    main()
