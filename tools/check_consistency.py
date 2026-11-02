#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_consistency.py — 找 Skill 内部的自相矛盾

这个项目最贵的教训
------------------
不是「漏了内容」，也不是「抄错数字」，而是：

  同一个 Skill 里，一处说「书里给了 X」，另一处说「书里没给 X」。

答题的 agent 从哪一头读起，就得到相反的结论。这种错最隐蔽——
因为单独看每一处都通顺，只有在整篇范围内才对撞得出来。

怎么检测
--------
1. 先确认「权威区」：`## DIMENSION*` 各节里出现过的**主题词**（术语表 + 标题）。
   这些是 Skill 说「我有这块内容」的地方。
2. 再扫「声明区」：Overview / When to Use / Critical Reminders / Query Response /
   Agent instruction / Output Format —— 这些地方经常残留旧的反面表述。
3. 若声明区出现「没给 / 不给 / 没有 / 未展开 / 不覆盖 / 不讨论 / 不管 …」
   并且同一句里带有某个**已被 DIMENSION 覆盖的主题词** → 报 CONFLICT。

用法
----
  python tools/check_consistency.py
  python tools/check_consistency.py --book 读财报 --verbose
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "books" / "04-技能"
BOOKS = ["笑傲牛熊", "股票魔法师", "读财报", "股市操练大全4"]

# 「说没有」的措辞
NEG = [
    r"没给", r"没有给", r"不给", r"未给",
    r"没有", r"未展开", r"没展开", r"未涉及", r"没有涉及",
    r"不覆盖", r"不讨论", r"不涉及", r"不管", r"不做",
    r"未明说", r"未定义", r"没定义", r"未提供", r"不提供",
]

NEG_RE = re.compile("|".join(NEG))

# ── 更精确的作用域匹配 ─────────────────────────────────────────
# 只靠「同一句里有否定词 + 有主题词」会大量误报：
#   「跌破均线多久算失效确实没定义」——否定的是「时长」，不是「均线」
#   「没有融资融券」——否定的是「融资融券」，不是「期货」
# 所以要求否定词与主题词**紧邻**（中间不允许跨逗号句号），
# 也就是「不给 X」「X 未展开」这种直接宾语结构。
SCOPE_GAP = r"[^，。；、！？\n]{0,8}"
FORWARD_TMPL = r"(?:没给|没有给|不给|未给|未提供|不提供|没有|未展开|没展开|未涉及|没有涉及|不覆盖|不讨论|不管|未明说|未定义|没定义){gap}{topic}"
BACKWARD_TMPL = r"{topic}{gap}(?:没给|没有|不给|未|没有涉及|未展开|不涉及|不管)"

# 权威区标记
AUTH_HEAD = re.compile(r"^## DIMENSION")

# 声明区：这些标题下的内容容易残留旧话
DECL_HEAD = re.compile(
    r"^## (Overview|When to Use This Skill|Critical Reminders|Query Response Framework|Output Format|Core Principle)"
)

# 主题词表：一个主题在 Skill 里叫什么。命中任意一个就算「这块有内容」。
TOPICS = {
    "止损": ["止损"],
    "仓位": ["仓位", "单只", "单票", "持仓量", "建仓比例"],
    "分散": ["分散", "持股数", "只股票", "篮子"],
    "选股": ["选股", "买什么"],
    "估值": ["估值", "DCF", "现金流折现", "清算价值", "市盈率", "PE"],
    "成交量": ["成交量", "放量", "量能"],
    "均线": ["均线", "移动平均"],
    "相对强度": ["相对强度", "RS", "RPS"],
    "四阶段": ["四阶段", "阶段判定", "第二阶段"],
    "期权": ["期权"],
    "期货": ["期货"],
    "卖空": ["卖空", "做空"],
    "杠杆": ["杠杆"],
    "审计意见": ["审计意见", "无保留"],
    "造假识别": ["造假"],
    "毛利率": ["毛利率"],
    "现金流": ["现金流"],
    "解套": ["解套", "摊低", "补仓"],
    "庄股": ["庄股"],
    "洗盘": ["洗盘"],
    "评级": ["评级", "安全系数"],
    "大盘择时": ["大盘", "择时"],
    "财报": ["财报", "财务报表"],
}


def classify(lines):
    """把文件切成 权威区 / 声明区，返回 (auth_text, decl_lines)"""
    auth, decl = [], []
    mode = None
    for i, line in enumerate(lines, 1):
        if line.startswith("## "):
            if AUTH_HEAD.match(line):
                mode = "auth"
            elif DECL_HEAD.match(line):
                mode = "decl"
            else:
                mode = "other"
        if mode == "auth":
            auth.append(line)
        elif mode == "decl":
            decl.append((i, line))
    return "\n".join(auth), decl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    books = [args.book] if args.book else BOOKS
    total_conflicts = 0

    for book in books:
        p = SKILL_DIR / book / "SKILL.md"
        if not p.exists():
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        auth_text, decl = classify(lines)

        # 权威区覆盖了哪些主题
        covered = set()
        for topic, kws in TOPICS.items():
            if any(kw in auth_text for kw in kws):
                covered.add(topic)

        conflicts = []
        for lineno, line in decl:
            if not NEG_RE.search(line):
                continue
            # 跳过修正句与疑问句：
            #   「不要说本书没讲 X」= 提醒，不是断言
            #   「别把估值说成本书不管」= 在纠正别人
            #   「有没有常见的造假痕迹」= 疑问，不是否定
            if re.search(r"不要说|别再说|不要只说|不是「没有|别把|≠", line):
                continue
            if "有没有" in line or "是否" in line or "能不能" in line:
                continue
            for topic in covered:
                hit_kw = None
                for kw in TOPICS[topic]:
                    fwd = re.compile(
                        FORWARD_TMPL.format(gap=SCOPE_GAP, topic=re.escape(kw))
                    )
                    bwd = re.compile(
                        BACKWARD_TMPL.format(gap=SCOPE_GAP, topic=re.escape(kw))
                    )
                    if fwd.search(line) or bwd.search(line):
                        hit_kw = kw
                        break
                if hit_kw:
                    conflicts.append((lineno, topic, hit_kw, line.strip()))
                    break  # 一句只报一次

        if conflicts:
            total_conflicts += len(conflicts)
            print(f"🔴 {book}：{len(conflicts)} 处可能的自相矛盾")
            for lineno, topic, kw, text in conflicts:
                print(f"   L{lineno}  [{topic}／关键字「{kw}」] DIMENSION 区有这块内容，这里却说没有")
                print(f"      {text[:110]}")
            print()
        else:
            print(f"✅ {book}：未发现自相矛盾")

        if args.verbose:
            print(f"   权威区覆盖主题 {len(covered)}：{'、'.join(sorted(covered))}\n")

    print("=" * 70)
    if total_conflicts:
        print(f"合计 {total_conflicts} 处需人工确认")
        print("处理原则：")
        print("  · 若 DIMENSION 区确实给了 → 删掉声明区的反面表述")
        print("  · 若 DIMENSION 区只是一笔带过 → 把声明区的说法改精确（限定范围）")
    else:
        print("✅ 全部一致")

    return 0


if __name__ == "__main__":
    sys.exit(main())
