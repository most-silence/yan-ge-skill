#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""spotcheck_merge.py — 抽查桶内归并质量

第一版错在哪（留作教训）
------------------------
第一版用「同一条规则下各候选的规则名相似度」判断是否压平，结果 7 个桶全线报红。

但看 B01-M01 的实际内容就明白：那条规则是「下单前先定性质并写死止损止盈线」，
下面挂 28 条候选包括「三种买卖模式」「先有止盈止损线才谈执行」——
这两个名字差异极大，但**都是该规则的组成部分**，归并没有错。

> **规则名是批读员每批各自起的，本来就应该千差万别。**
> 名字不同不等于归并错误。用名字相似度判断归并质量，方法本身就错了。

正确该看什么
------------
1. **规则内部是否自相矛盾**：同一规则下写了两个互斥的动作
2. **对账表是否完整**：N 条候选是否全部有下落，编号连不连续
3. **单列率是否异常**：单列过多说明归并能力不足
4. **边界声明是否存在**：好归并会写「本条只收 X，Y 归 M06」这种边界
5. **候选跨度是否合理**：跨度过大 + 规则内容极简 → 可疑

第 4 条是判断归并质量最有效的信号——愿意写边界的归并员，
通常是真的想过「这条和那条的界线在哪」。
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MERGE_DIR = ROOT / "sources" / "05-播客转写" / "_归并"
BUCKET_DIR = ROOT / "sources" / "05-播客转写" / "_分桶"
OUT_MD = ROOT / "sources" / "05-播客转写" / "_归并抽查.md"

# 对账表行：| B18-001 | → M01 |  或  | B18-001 | → A |
RECON_RE = re.compile(r"^\|\s*([A-Z]\d{2}-\d{3})\s*\|\s*(.+?)\s*\|\s*$", re.M)
# 规则标题（兼容三种排版）
#
# 教训：第一版只认 `###`，结果 B18 里 `###` 是**分组标题**（A/B/C…），
# 真规则在 `####`（A01/A02…）。于是 79 条规则被数成 16 条，
# 归并比虚高到 38.9:1，全部误报「疑似压平」。
# 检测工具自己先要验证——不能拿错误的基数去判对错。
#
# 第二课：B03 用了 `S01`~`S06` 当单列编号。切块时若不认 S 系，
# 块边界会错位，下一个块的字段被算进上一个块 → 31 条误报「缺字段」。
# 所以编号前缀要全收：M / S / 字母+数字 / B18-M 形式。
#
# 第三课：B06 有 `M01-A` 这种子编号，`[A-Z]\d{2}-M\d+` 匹配不到尾部 `-A`。
# 编号统一放宽成 `[\w-]+`，让所有变体都进得来。
RULE_HDR_RES = [
    re.compile(r"^#{3,4}\s+([A-Z]\d{2}-M\d+(?:-[A-Z])?)\s*[·.]\s*(.+)$", re.M),
    re.compile(r"^#{3,4}\s+(M\d+(?:-[A-Z])?)\s*[·.]\s*(.+)$", re.M),
    re.compile(r"^#{3,4}\s+(S\d+(?:-[A-Z])?)\s*[·.]\s*(.+)$", re.M),
    re.compile(r"^#{3,4}\s+([A-Z]\d{2})\s*[·.]\s*(.+)$", re.M),
]
# 任何 #### 级标题都算块边界（用于切块，不用于计数）
ANY_BLOCK_HDR = re.compile(r"^#{3,4}\s+[A-Z][\w-]*\s*[·.]", re.M)
# 桶内候选块：## B18-001 · 规则名
CAND_RE = re.compile(r"^##\s+([A-Z]\d{2}-\d{3})\s*[·.]\s*(.+)$", re.M)


def parse_recon(text):
    """对账表：候选编号 → 规则编号

    ⚠️ 对账表有**两种排版**：
        单栏：  | B09-001 | → M29 |
        四栏：  | B09-001 | → M29 | B09-101 | → M03 | B09-201 | → M20 | B09-301 | → M34 |

    B09 用了四栏并排，第一版正则以整行为单位，只能抓到每行的第一对，
    401 行只认出 101 行 → 误报「缺 300 个编号」。

    正确做法：在每一行里**反复**找 `| 编号 | → 规则 |` 这样的配对。
    """
    out = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # 四栏并排时 cells = [编号, →M29, 编号, →M03, ...]
        for k in range(len(cells) - 1):
            cid = cells[k]
            # 候选编号有两种写法：B18-001（带短横线）与 X001（不带）
            if not re.fullmatch(r"[A-Z]\d{2}-\d{3}|[A-Z]\d{3,4}", cid):
                continue
            dest = cells[k + 1]
            dm = re.search(
                r"([A-Z]\d{2}-M\d+(?:-[A-Z])?|M\d+(?:-[A-Z])?|S\d+|[A-Z]\d{2})\b", dest)
            out[cid] = dm.group(1) if dm else dest[:20]
    return out


def parse_rules(text):
    """规则编号 → 规则名

    ⚠️ 两级标题：
        ### A · 指数选择与分工        ← 分组，不是规则
        #### A01 · 小资金直接买 ETF    ← 这才是规则

    踩过两个坑：
      ① 只认 `###` → B18 的 79 条规则被数成 16 条，归并比虚高到 38.9:1
      ② 用 `break` 在第一个命中的正则上停 → B18 里先匹配到几个 `M01`，
         于是没跑「A01」那条正则，仍然只数到 20 条

    所以：**收集所有正则的命中，合并去重**，并且排除裸字母分组标题。
    """
    out = {}
    for rx in RULE_HDR_RES:
        for rid, name in rx.findall(text):
            # 裸字母（A/B/C）是分组标题，不是规则——只有找不到带编号规则时才用
            if re.fullmatch(r"[A-Z]", rid):
                continue
            out.setdefault(rid, name.strip())
    if out:
        return out
    # 退路：这份产出确实只用了裸字母当规则
    for m in re.finditer(r"^#{3,4}\s+([A-Z])\s*[·.]\s*(.+)$", text, re.M):
        out.setdefault(m.group(1), m.group(2).strip())
    return out


def parse_cands(text):
    """候选编号 → (规则名, 正文片段)"""
    out = {}
    marks = [(m.start(), m.group(1), m.group(2).strip()) for m in CAND_RE.finditer(text)]
    for i, (pos, cid, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out[cid] = (name, text[pos:end])
    return out


def grammar_boundary(text):
    """统计有多少条规则写了边界声明

    「本条只收 X，Y 归 M06」这类声明是归并质量最强的信号：
    愿意写边界的归并员，是真的想过「这条和那条的界线在哪」。
    """
    pats = [
        r"本条只收", r"本条只", r"归 [A-Z]\d{2}-M\d+", r"归 M\d+",
        r"与 [A-Z]?\d*-?M?\d+ 有重叠", r"交叉 M\d+", r"主动作归",
    ]
    return sum(1 for p in pats if re.search(p, text))


def check_rules(text, rules):
    """逐条检查规则的完整性与自相矛盾

    踩过的坑：切块时只用 RULE_HDR_RES（`###` 和 `####`），
    但 B03 的规则标题是 `### M01 · ...`，而「归并总表」里也有 `| M01 |` 这样的表格行。
    第一版把整篇文档按标题切，结果每个块的正文里都混进了别的规则的表行，
    「触发条件」在下一块里，于是 31 条全部误报「缺字段」。

    正确做法：只从「## 二、逐条展开」之后开始切，
    并且块的范围到**下一个同级或更高级标题**为止。
    """
    # 定位「逐条展开」段落，避免把总表、对账表混进来
    m = re.search(r"^##\s*二[、.]", text, re.M)
    body_text = text[m.start():] if m else text
    # 到「## 三、」或「## 四、」为止
    m2 = re.search(r"^##\s*[三四][、.]", body_text, re.M)
    if m2:
        body_text = body_text[:m2.start()]

    marks = []
    for mm in ANY_BLOCK_HDR.finditer(body_text):
        rid = re.match(r"^#{3,4}\s+([A-Z][\w-]*)", mm.group(0))
        if rid and not re.fullmatch(r"[A-Z]", rid.group(1)):
            marks.append((mm.start(), rid.group(1)))
    marks.sort()

    blocks = {}
    seen = set()
    for i, (pos, rid) in enumerate(marks):
        if rid in seen:
            continue
        seen.add(rid)
        end = marks[i + 1][0] if i + 1 < len(marks) else len(body_text)
        blocks[rid] = body_text[pos:end]

    issues = []
    for rid, body in blocks.items():
        # 子规则（M01-A）不要求自带完整字段——它继承父规则的结构。
        is_child = bool(re.search(r"-[A-Z]$", rid))
        # 单列项（S01/S02）是「无法归并、单独留档」的候选，
        # 本来就不成规则，只要求写清为什么单列，不要求触发/动作齐全。
        is_single = bool(re.fullmatch(r"S\d+(?:-[A-Z])?", rid))
        if not is_child and not is_single:
            miss = [n for n in ("触发条件", "动作") if n not in body]
            if miss:
                issues.append((rid, "缺字段", "、".join(miss), 2))
        # 子规则（M17-A）与单列项继承父级/自身的说明，不强制自带引文。
        # 只有独立主规则缺引文才算硬问题。
        if not is_child and not is_single:
            if ">" not in body and "原话" not in body:
                issues.append((rid, "无原话", "整条没有引文", 3))
            elif "待补" in body:
                issues.append((rid, "原话待补", "候选未附引文", 1))
        # 自相矛盾：只在「动作」那一段里判，避免被备注里的冲突说明误伤
        #
        # ⚠️ 这个检查天生粗糙。「到止损线只有两条路：补仓或止损」——
        # 动作里同时有「止损」和「加仓」，但那是规则本身如此，不是矛盾。
        # 所以「自相矛盾」只作为人工复核的提示，不能当缺陷计数。
        am = re.search(r"\*\*动作\*\*[^\n]*\n?(.{0,500})", body, re.S)
        if am:
            seg = am.group(1)
            for a, b in [("走", "拿")]:
                if a in seg and b in seg:
                    issues.append((rid, "可能自相矛盾", f"动作里同时有「{a}」和「{b}」", 1))
                    break
    return issues, len(blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", default=None, help="只查某个桶，如 B18")
    args = ap.parse_args()

    files = sorted(MERGE_DIR.glob("*.md"))
    if args.bucket:
        files = [f for f in files if f.name.startswith(args.bucket)]
    if not files:
        print("没有归并产出可查", file=sys.stderr)
        return 1

    L = []
    A = L.append
    A("# 线3 播客 · 归并质量抽查")
    A("")
    A("> 生成：2026-11-01 ｜ 工具：`tools/spotcheck_merge.py`")
    A("")
    A("## 在查什么")
    A("")
    A("第一版用「同一条规则下各候选的规则名相似度」判断是否压平，7 个桶全线报红。")
    A("但看 B01-M01 就明白那是误判——那条规则是「下单前先定性质并写死止损止盈线」，")
    A("下面挂的「三种买卖模式」「先有止盈止损线才谈执行」名字差异极大，")
    A("**但都是该规则的组成部分**。")
    A("")
    A("> 规则名是批读员每批各自起的，本来就应该千差万别。")
    A("> 名字不同不等于归并错误。**用名字相似度判断归并质量，方法本身就错了。**")
    A("")
    A("这一版改查六件事：")
    A("")
    A("| # | 查什么 | 判据 |")
    A("|---|---|---|")
    A("| 1 | 对账表完整性 | N 条候选是否全部有下落，编号连续无缺 |")
    A("| 2 | 单列率 | 单列/无法归并占比过高 = 归并能力不足 |")
    A("| 3 | 规则要素 | 每条是否都写了触发条件 + 动作 |")
    A("| 4 | 引文 | 是否有原话；标「待补」的说明诚实，不算缺陷 |")
    A("| 5 | 自相矛盾 | 同一规则的动作段里出现互斥动作 |")
    A("| 6 | 边界声明 | 有没有写「本条只收 X，Y 归 M06」这种界线 |")
    A("")
    A("> 第 6 条是判断归并质量最有效的信号——愿意写边界的归并员，")
    A("> 是真的想过「这条和那条的界线在哪」。")
    A("")
    A("---")
    A("")

    summary = []
    for f in files:
        code = f.name.split("-")[0]
        text = f.read_text(encoding="utf-8")
        recon = parse_recon(text)
        rules = parse_rules(text)
        issues, n_blocks = check_rules(text, rules)
        n_boundary = grammar_boundary(text)

        by_rule = defaultdict(list)
        unmapped = []
        for cid, dest in recon.items():
            rid = re.search(r"([A-Z]\d{2}-M\d+|M\d+|[A-Z]\d{2})\b", dest)
            key = rid.group(1) if rid else dest
            if "单列" in dest or "无法归并" in dest or key in ("—", ""):
                unmapped.append(cid)
            else:
                by_rule[key].append(cid)

        ratio = len(recon) / len(rules) if rules else 0
        unmapped_pct = len(unmapped) / len(recon) * 100 if recon else 0

        # 编号连续性
        nums = sorted(int(c.split("-")[1]) for c in recon if "-" in c)
        gaps = []
        if nums:
            full = set(range(1, max(nums) + 1))
            gaps = sorted(full - set(nums))

        A(f"## {code} ｜ {len(recon)} 候选 → {len(rules)} 规则（{ratio:.1f}:1）")
        A("")
        A("| 项 | 值 | 判读 |")
        A("|---|---|---|")
        A(f"| 对账表 | {len(recon)} 条有下落 | {'✅' if not gaps else f'🔴 缺 {len(gaps)} 个编号'} |")
        A(f"| 单列/无法归并 | {len(unmapped)} 条（{unmapped_pct:.1f}%） | "
          f"{'✅' if unmapped_pct < 8 else '🟡 偏高'} |")
        A(f"| 规则要素不全 | {sum(1 for i in issues if i[1]=='缺字段')} 条 | "
          f"{'✅' if not any(i[1]=='缺字段' for i in issues) else '🔴'} |")
        A(f"| 无引文/待补 | {sum(1 for i in issues if '原话' in i[1])} 条 | "
          f"{'✅' if not any(i[1]=='无原话' for i in issues) else '🟡'} |")
        A(f"| 自相矛盾 | {sum(1 for i in issues if '矛盾' in i[1])} 条 | "
          f"{'✅' if not any('矛盾' in i[1] for i in issues) else '🔴'} |")
        A(f"| 边界声明 | {n_boundary} 处 | {'✅ 有界线意识' if n_boundary >= 3 else '🟡 偏少'} |")
        A("")

        if gaps:
            A(f"**🔴 对账表缺编号**：{gaps[:20]}{' …' if len(gaps)>20 else ''}")
            A("")
        if issues:
            A("**问题明细**：")
            A("")
            for rid, kind, desc, sev in issues[:12]:
                mark = "🔴" if sev >= 2 else "🟡"
                A(f"- {mark} **{rid}** {kind}：{desc}")
            if len(issues) > 12:
                A(f"- …… 另有 {len(issues)-12} 条")
            A("")

        # 挂载最多的 3 条规则，人工可复核
        top = sorted(by_rule.items(), key=lambda x: -len(x[1]))[:3]
        if top:
            A("**候选最集中的 3 条规则**（供人工复核对账是否合理）：")
            A("")
            for rid, cids in top:
                A(f"- **{rid}** {rules.get(rid,'')[:44]} — {len(cids)} 条候选")
            A("")

        summary.append({
            "code": code, "cands": len(recon), "rules": len(rules),
            "ratio": round(ratio, 1), "unmapped": len(unmapped),
            "gaps": len(gaps),
            "hard": sum(1 for i in issues if i[3] >= 2),
            "soft": sum(1 for i in issues if i[3] < 2),
            "boundary": n_boundary,
        })
        A("---")
        A("")

    A("## 汇总")
    A("")
    A("| 桶 | 候选 | 规则 | 归并比 | 单列 | 缺编号 | 硬问题 | 软问题 | 边界声明 | 判读 |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for s in summary:
        if s["gaps"] or s["hard"] >= 3:
            verdict = "🔴 需复核"
        elif s["hard"] or s["unmapped"] > s["cands"] * 0.1:
            verdict = "🟡 抽查"
        else:
            verdict = "✅ 通过"
        A(f"| {s['code']} | {s['cands']} | {s['rules']} | {s['ratio']} | "
          f"{s['unmapped']} | {s['gaps']} | {s['hard']} | {s['soft']} | "
          f"{s['boundary']} | {verdict} |")
    A("")
    A("> **归并比高本身不是问题。** B18「大盘/指数」623 条归成 163 条，")
    A("> 若大量候选本来就是「今天上证怎么怎么样」的当日复述，归并比高恰恰说明做对了。")
    A("> 真正要看的是对账表完整、要素齐全、边界清楚。")
    A("")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"抽查 {len(files)} 个桶\n")
    print(f"{'桶':<5}{'候选':>6}{'规则':>6}{'归并比':>8}{'单列':>6}{'缺号':>6}{'硬':>4}{'软':>4}{'边界':>6}  判读")
    for s in summary:
        if s["gaps"] or s["hard"] >= 3:
            mark = "🔴"
        elif s["hard"] or s["unmapped"] > s["cands"] * 0.1:
            mark = "🟡"
        else:
            mark = "✅"
        print(f"{s['code']:<5}{s['cands']:>6}{s['rules']:>6}{s['ratio']:>8.1f}"
              f"{s['unmapped']:>6}{s['gaps']:>6}{s['hard']:>4}{s['soft']:>4}"
              f"{s['boundary']:>6}  {mark}")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
