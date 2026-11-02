#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""triage_quotes.py — 甄别「全不中」引文：是格式差异，还是真编造

为什么需要这一步
----------------
`verify_quotes.py` 报「全不中」有 48 条。但这 48 条不能一律当编造处理——

  可能 A：引文跨了多行/多个时间戳，工具切分方式不对 → 假失败
  可能 B：批读者把分散在不同时间戳的句子拼成了一句 → 真违规（模板明令禁止）
  可能 C：批读者改写了词句 → 真润色
  可能 D：数字/专名写错（如 4125 写成 4152） → 真抄错
  可能 E：整条是凭理解编的，原文没有 → 真编造

五类处置完全不同：A 修工具，B/C/D 该条返工，E 该批返工。

判定方法
--------
对每条「全不中」，取引文里**最长的连续片段**去原文找：

  找到 >80% 字 → A 格式问题
  找到 40–80%  → B 拼接（真的把远处的话拼在一起了）
  找到 10–40%  → C/D 改写或错字
  找到 <10%    → E 编造

「连续片段」用最长公共子串实现——比逐词匹配更能区分「拼接」和「改写」。
"""
import argparse
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "vq", Path(__file__).resolve().parent / "verify_quotes.py")
vq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vq)

ROOT = Path(__file__).resolve().parent.parent
OUT_MD = ROOT / "sources" / "05-播客转写" / "_引文甄别.md"
OUT_JSON = ROOT / "sources" / "05-播客转写" / "_引文甄别.json"


def longest_common(a, b):
    """最长公共子串长度（a 是短串，b 是长串）"""
    sm = SequenceMatcher(None, a, b, autojunk=False)
    m = sm.find_longest_match(0, len(a), 0, len(b))
    return m.size


def strip_ts(text):
    """去掉行内时间戳 [00:12:34]

    2026-10-31 修正：第一版忘了这一步，引文里的 `[00:12:34]` 被当成正文参与比对，
    导致相似度被系统性压低（一条本应 0.9 的引文算出来只有 0.3），
    E 类和 C 类被大量误判。
    """
    return vq.TS_RE.sub("", text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default=None)
    args = ap.parse_args()

    srcs = vq.build_sources()
    cand = ROOT / "sources" / "05-播客转写" / "_规则候选"
    files = ([cand / f"batch-{args.batch}.md"] if args.batch
             else sorted(cand.glob("batch-*.md")))
    files = [f for f in files if f.exists()]

    rows = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for q, eid in vq.QUOTE_MULTI_RE.findall(text):
            q = vq.clean_quote(q)
            src = srcs.get(eid)
            if src is None:
                continue
            frags = vq.split_frags(q)
            if not frags:
                continue
            src_n = vq.norm(src)
            hit = sum(1 for fr in frags if vq.norm(fr) in src_n)
            if hit == len(frags):
                continue  # 全中的不用甄别

            qn = vq.norm(strip_ts(q))
            lcs = longest_common(qn, src_n)
            ratio = lcs / len(qn) if qn else 0

            if ratio > 0.8:
                cat, label = "A", "格式问题（工具切分不对）"
            elif ratio >= 0.4:
                cat, label = "B", "拼接（把远处的话并成一句）"
            elif ratio >= 0.1:
                cat, label = "C", "改写或错字"
            else:
                cat, label = "E", "编造（原文几乎没有）"

            rows.append({
                "file": f.name, "eid": eid, "cat": cat, "label": label,
                "hit": hit, "total": len(frags),
                "lcs_ratio": round(ratio, 3), "quote": q[:160],
            })

    order = {"A": 0, "B": 1, "C": 2, "E": 3}
    rows.sort(key=lambda r: (order[r["cat"]], r["file"]))

    from collections import Counter
    cnt = Counter(r["cat"] for r in rows)

    OUT_JSON.write_text(__import__("json").dumps(
        {"total_bad": len(rows), "by_cat": dict(cnt), "rows": rows},
        ensure_ascii=False, indent=2), encoding="utf-8")

    L = []
    A = L.append
    A("# 线3 播客 · 引文失败甄别")
    A("")
    A("> 生成：2026-10-31 ｜ 工具：`tools/triage_quotes.py`")
    A(f"> 甄别对象：`verify_quotes.py` 判为「部分/全不中」的引文，共 **{len(rows)}** 条")
    A("")
    A("## 一、为什么不能一律当编造")
    A("")
    A("「全不中」有五种成因，处置完全不同：")
    A("")
    A("| 类别 | 成因 | 处置 |")
    A("|---|---|---|")
    A("| **A** | 引文跨多行/多时间戳，工具切分不对 | **修工具**，不是批读的错 |")
    A("| **B** | 把分散在不同时间戳的句子拼成一句 | 该条**返工**（模板明令禁止） |")
    A("| **C** | 改写词句或写错数字/专名 | 该条**返工**回原文改 |")
    A("| **E** | 原文几乎没有这段话 | **该批返工**，批读不可信 |")
    A("")
    A("判定方法：取引文本身去原文找最长连续公共子串，看占引文的比例。")
    A("")
    A("| 比例 | 判为 | 含义 |")
    A("|---|---|---|")
    A("| >80% | A | 基本全对，只是切分问题 |")
    A("| 40–80% | B | 有整块对得上，但有跳跃 → 拼接 |")
    A("| 10–40% | C | 只对得上零碎词 → 改写/错字 |")
    A("| <10% | E | 几乎完全对不上 → 编造 |")
    A("")
    A("## 二、结果")
    A("")
    A("| 类别 | 条数 |")
    A("|---|---:|")
    for k in ("A", "B", "C", "E"):
        A(f"| {k} · { {'A':'格式问题','B':'拼接','C':'改写/错字','E':'编造'}[k] } | **{cnt.get(k, 0)}** |")
    A(f"| 合计 | **{len(rows)}** |")
    A("")
    bad_real = cnt.get("B", 0) + cnt.get("C", 0) + cnt.get("E", 0)
    A(f"> 真正的批读质量问题（B+C+E）：**{bad_real}** 条"
      f"（占全部引文约 {bad_real / max(len(rows), 1) * 100:.1f}% 的失败样本中）。")
    A("")
    for cat, title in (("E", "E 类 · 编造（最严重，需整批返工）"),
                       ("B", "B 类 · 拼接"),
                       ("C", "C 类 · 改写/错字"),
                       ("A", "A 类 · 格式问题（修工具即可）")):
        gs = [r for r in rows if r["cat"] == cat]
        if not gs:
            continue
        A(f"## {title}（{len(gs)} 条）")
        A("")
        A("| 批次 | 期次 | 命中 | 相似度 | 引文 |")
        A("|---|---|---:|---:|---|")
        for r in gs[:40]:
            q = r["quote"].replace("|", "｜")[:90]
            A(f"| {r['file']} | `{r['eid']}` | {r['hit']}/{r['total']} "
              f"| {r['lcs_ratio']:.2f} | {q} |")
        if len(gs) > 40:
            A(f"| … | | | | 还有 {len(gs) - 40} 条 |")
        A("")
    A("---")
    A("")
    A("> **合规**：本文件仅为研究学习其公开表达，不构成投资建议。")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"甄别 {len(rows)} 条失败引文")
    for k in ("A", "B", "C", "E"):
        print(f"  {k}: {cnt.get(k, 0)}")
    print(f"\n→ {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
