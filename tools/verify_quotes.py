#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_quotes.py — 校验批读产出里的「原话」是否逐字存在于转写稿

为什么必须有这一步
------------------
批读模板的第一条铁律是「原话必须逐字摘录」。但**铁律本身不会自动执行**——
LLM 写「逐字摘录」时仍会顺手润色、补全、合并重复句。

如果不校验，整条审计链会在最源头断掉：
  原话被润色 → 时间戳对不上 → 拿去做盲评时「这不是他说的」→ SKILL 的可信度归零

玟火 `material-hygiene.md` §1：「转写稿不润色。表达 DNA 藏在口语里。润色一次，销毁一次。」
这句话约束的是**抽取者**，所以抽取者的产出必须可验证。

三档判定
--------
  全中    所有 >6 字的片段都能在原文找到
  部分    部分片段找到 → 可能是正常省略（`……`），也可能是编造，需人看
  全不中  一个都找不到 → 高度可疑，几乎肯定是编的或抄错期次

用法
----
  python tools/verify_quotes.py                    # 校验全部批次
  python tools/verify_quotes.py --batch 02         # 只校验 batch-02
  python tools/verify_quotes.py --strict           # 部分=失败
"""

import argparse
import glob
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXT_DIR = ROOT / "sources" / "05-播客转写" / "audio_txt"
CAND_DIR = ROOT / "sources" / "05-播客转写" / "_规则候选"
OUT_MD = ROOT / "sources" / "05-播客转写" / "_原话校验.md"

# 引用块有三种格式，都要认：
#   ① 单行：  > 「原话」 —— `eid` `[ts]`
#   ② 多行：  > 「[00:11:59] 第一行
#             > [00:12:01] 第二行」 —— `eid` `[ts]`
#   ③ 逐行：  > [00:00:23] 第一行
#             > [00:00:42] 第二行
#
#             —— `eid` `[00:00:23]`~`[00:00:42]`
#
# ③ 是 batch-09 用的，格式最好——保留原文行结构，最不可能串话。
# 第一版只认 ①，第二版认 ①②，这是第三版，三种都认。
QUOTE_MULTI_RE = re.compile(
    r"^> 「(.+?)」 —— `([A-Za-z0-9]+)`",
    re.M | re.S,
)
# ③ 型：连续的 "> [ts] ..." 行，末尾跟 "—— `eid` `[t1]`~`[t2]`"
QUOTE_STANZA_RE = re.compile(
    r"((?:^> \[\d{2}:\d{2}:\d{2}\].*\n)+)\s*\n?—— `([A-Za-z0-9]+)`",
    re.M,
)

TS_RE = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]")

# 标点/空白归一：判断「逐字」的正确口径是**词语序列一致**，不是标点一致。
# ASR 原稿用半角逗号，批读者常规范成全角或空格——这不是润色，不该判失败。
# 真正的润色是改写词句，那个归一化之后仍然对不上。
_PUNCT = re.compile(r"[\s，。、,.!！?？;；:：\"\"''「」『』()（）\[\]【】—…~·`´]")


def norm(text):
    """去标点、去空白、去时间戳，只留词"""
    t = TS_RE.sub("", text)
    return _PUNCT.sub("", t)


def build_sources():
    """eid → 清洗稿全文（去时间戳后的纯文本用于片段比对）"""
    out = {}
    for p in glob.glob(str(TXT_DIR / "*._clean.txt")):
        name = Path(p).name
        eid = name.split("_")[0]
        try:
            out[eid] = Path(p).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
    return out


def extract_quotes(text):
    """抽出所有引文，返回 [(引文正文, eid)]

    兼容两种排版：
      ①② 型：`> 「...」 —— `eid``
      ③  型：连续 `> [ts] 行` + 空行 + `—— `eid` `[t1]`~`[t2]``

    ③ 型的行首 "> " 由 clean_quote 去掉。
    """
    out = []
    # ①② 型
    for m in QUOTE_MULTI_RE.finditer(text):
        out.append((m.group(1), m.group(2)))
    # ③ 型（若同一位置已被 ①② 抓到会重复，这里只在没有 ①② 匹配的批次启用）
    if not out:
        for m in QUOTE_STANZA_RE.finditer(text):
            out.append((m.group(1), m.group(2)))
    return out


def split_frags(text):
    """把引文切成语义片段

    切分点：两段以上空白、省略号。短于 6 字的片段丢弃（「对吧」「是吧」这类
    在原文里到处都是，验不出真伪，反而制造假通过）。

    ⚠️ 单片段（整条引文没有切分点）必须**整条**验证，不能过 `> 6` 字的门槛就放过。
    第一版这里有个隐患：如果整条引文很长但没切分点，它就变成一个巨大片段，
    只要有一个字不同就判「全不中」——那是标点/口误差异，不是编造。
    解决：整条比对前先归一（去标点），归一后整条在原文里 → 全中。
    """
    core = TS_RE.sub(" ", text)
    frags = re.split(r"\s{2,}|…+|\.{3,}", core)
    return [f.strip() for f in frags if len(norm(f)) > 6]


def clean_quote(raw):
    """把多行引文拉平成一行，去掉行首的 "> "

    多行格式：
        > 「[00:11:59] 第一行
        > [00:12:01] 第二行」
    要还原成「[00:11:59] 第一行 [00:12:01] 第二行」
    """
    parts = []
    for ln in raw.splitlines():
        s = ln.lstrip(">").strip()
        if s:
            parts.append(s)
    return " ".join(parts).strip("「」")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default=None, help="只校验某一批，如 02")
    ap.add_argument("--strict", action="store_true", help="部分命中也算失败")
    args = ap.parse_args()

    srcs = build_sources()
    if not srcs:
        print("找不到清洗稿", file=sys.stderr)
        return 1

    if args.batch:
        files = [CAND_DIR / f"batch-{args.batch}.md"]
    else:
        files = sorted(CAND_DIR.glob("batch-*.md"))
    files = [f for f in files if f.exists()]
    if not files:
        print("没有批读产出可校验", file=sys.stderr)
        return 1

    rows, verdict_cnt = [], Counter()
    weak = []

    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        quotes = extract_quotes(text)
        if not quotes:
            print(f"! {f.name} 里没找到引用块（格式可能不符）", file=sys.stderr)
            continue
        for q, eid in quotes:
            src = srcs.get(eid)
            q = clean_quote(q)
            if src is None:
                rows.append({"file": f.name, "eid": eid, "verdict": "期次不存在",
                             "hit": 0, "total": 0, "quote": q[:100]})
                verdict_cnt["期次不存在"] += 1
                continue
            frags = split_frags(q)
            if not frags:
                continue
            src_n = norm(src)
            hit = sum(1 for fr in frags if norm(fr) in src_n)
            if hit == len(frags):
                verdict = "全中"
            elif hit:
                verdict = "部分"
            else:
                verdict = "全不中"
            verdict_cnt[verdict] += 1
            rows.append({"file": f.name, "eid": eid, "verdict": verdict,
                         "hit": hit, "total": len(frags), "quote": q[:120]})
            if verdict != "全中" or (args.strict and verdict == "部分"):
                weak.append(rows[-1])

    total = sum(verdict_cnt.values())
    ok = verdict_cnt.get("全中", 0)
    rate = ok / total * 100 if total else 0

    # ── MD ──
    L = []
    A = L.append
    A("# 线3 播客 · 原话校验")
    A("")
    A("> 生成：2026-10-31 ｜ 工具：`tools/verify_quotes.py`")
    A(f"> 校验批次：**{len(files)}** ｜ 引用块：**{total}** 条")
    A("")
    A("## 一、为什么必须校验")
    A("")
    A("批读模板第一条铁律是「原话必须逐字摘录」。但**铁律本身不会自动执行**——")
    A("LLM 写「逐字摘录」时仍会顺手润色、补全、合并重复句。不校验的话，")
    A("整条审计链会在最源头断掉：")
    A("")
    A("```")
    A("原话被润色 → 时间戳对不上 → 盲评时「这不是他说的」→ SKILL 可信度归零")
    A("```")
    A("")
    A("> 玟火 `material-hygiene.md` §1：「转写稿不润色。表达 DNA 藏在口语里。润色一次，销毁一次。」")
    A("> 这句话约束的是**抽取者**，所以抽取者的产出必须可验证。")
    A("")
    A("## 二、判定口径")
    A("")
    A("| 判定 | 含义 |")
    A("|---|---|")
    A("| **全中** | 所有 >6 字的片段都能在原文找到 |")
    A("| **部分** | 部分找到 → 可能是正常省略（`……`），也可能是编造，需人看 |")
    A("| **全不中** | 一个都找不到 → 高度可疑，几乎肯定是编的或抄错期次 |")
    A("| **期次不存在** | 引用的 eid 在语料里没有 |")
    A("")
    A("> 短于 6 字的片段丢弃。理由：「对吧」「是吧」在原文里到处都是，验不出真伪，")
    A("> 反而制造假通过。")
    A("")
    A("## 三、结果")
    A("")
    A("| 判定 | 条数 | 占比 |")
    A("|---|---:|---:|")
    for k in ("全中", "部分", "全不中", "期次不存在"):
        n = verdict_cnt.get(k, 0)
        if not n:
            continue
        A(f"| {k} | **{n}** | {n / total * 100:.1f}% |")
    A(f"| 合计 | **{total}** | 100% |")
    A("")
    A(f"**逐字率：{rate:.1f}%**")
    A("")
    if rate >= 95:
        A("> ✅ 逐字率 ≥95%，批读铁律执行到位。")
    elif rate >= 85:
        A("> 🟡 逐字率 85–95%，存在润色倾向，需抽查「部分」条目。")
    else:
        A("> 🔴 逐字率 <85%，批读质量不达标，**该批需返工**。")
    A("")
    if weak:
        A(f"## 四、非全中条目（{len(weak)} 条）")
        A("")
        A("| 批次 | 期次 | 判定 | 命中 | 引文 |")
        A("|---|---|---|---:|---|")
        for r in weak[:80]:
            q = r["quote"].replace("|", "｜")[:80]
            A(f"| {r['file']} | `{r['eid']}` | {r['verdict']} "
              f"| {r['hit']}/{r['total']} | {q} |")
        if len(weak) > 80:
            A(f"| … | | | | 还有 {len(weak) - 80} 条 |")
        A("")
        A("> **「部分」不等于错。** 正常省略（用 `……` 跳过中间的话）会导致部分命中。")
        A("> 需要人看的是：省略处有没有改变语义。若改变 → 该条返工。")
    A("")
    A("---")
    A("")
    A("> **合规**：本文件仅为研究学习其公开表达，不构成投资建议。")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"校验 {len(files)} 批 / {total} 条引用")
    for k in ("全中", "部分", "全不中", "期次不存在"):
        if verdict_cnt.get(k):
            print(f"  {k}: {verdict_cnt[k]}")
    print(f"逐字率: {rate:.1f}%")
    if weak:
        print(f"\n非全中 {len(weak)} 条，前 5：")
        for r in weak[:5]:
            print(f"  [{r['verdict']} {r['hit']}/{r['total']}] {r['quote'][:70]}")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
