#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""repair_quotes.py — 用原文真实文本替换批读产出里的失败引文

为什么能自动修
--------------
批读者写引文时保留了两样可定位的东西：**期次 ID** 和**行内时间戳**。
这两样足以在原文里精确定位——只要时间戳对得上，原文那几行就是他真正说过的话。

所以返工不是「重读一遍」，而是：
  1. 从失败引文里抽出行内时间戳序列
  2. 拿这些时间戳去原文取对应行
  3. 用原文行拼成新引文，替换旧的
  4. 保留原有的 `—— eid [ts]` 归属，不动

这样修出来的引文 **100% 逐字**，因为它就是从原文复制的。

修不了的怎么办
--------------
时间戳对不上原文（编造时时间戳也是编的）→ 写进 `_引文待重读.md`，人工处理。
这类必须回原文重找，不能猜。

用法
----
  python tools/repair_quotes.py --dry-run    # 只报告，不改文件
  python tools/repair_quotes.py              # 实际修
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "vq", Path(__file__).resolve().parent / "verify_quotes.py")
vq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vq)

ROOT = Path(__file__).resolve().parent.parent
CAND_DIR = ROOT / "sources" / "05-播客转写" / "_规则候选"
OUT_UNFIXABLE = ROOT / "sources" / "05-播客转写" / "_引文待重读.md"

LINE_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$")


def load_lines():
    """eid → {时间戳: 正文行}

    同时返回 eid → 全文（去标点归一后的），供失败判定用。
    """
    out, full = {}, {}
    import glob
    for p in glob.glob(str(vq.TXT_DIR / "*._clean.txt")):
        name = Path(p).name
        eid = name.split("_")[0]
        d = {}
        raw = []
        for ln in Path(p).read_text(encoding="utf-8", errors="ignore").splitlines():
            m = LINE_RE.match(ln)
            if m:
                d[m.group(1)] = m.group(2)
                raw.append(m.group(2))
        out[eid] = d
        full[eid] = vq.norm(" ".join(raw))
    return out, full


def rebuild(q, eid, lines_by_ep):
    """用原文行重建引文

    返回 (新引文, 状态)
      状态 full  = 所有时间戳都对上，全部用原文替换
      状态 part  = 部分时间戳对上，能换的换，换不了的保留原样并标 ⚠️
      状态 none  = 一个都对不上 → 不可修
    """
    lines = lines_by_ep.get(eid, {})
    ts_list = vq.TS_RE.findall(q)
    if not ts_list:
        return None, "none"

    got, missing = [], []
    for ts in ts_list:
        if ts in lines:
            got.append((ts, lines[ts]))
        else:
            missing.append(ts)

    if not got:
        return None, "none"
    if missing:
        # 部分修：把对得上的原文行拼回去，缺的标出来
        body = " ".join(f"[{ts}] {txt}" for ts, txt in got)
        body += f"  ⚠️缺 {len(missing)} 个时间戳：{'、'.join(missing[:3])}"
        return body, "part"
    body = " ".join(f"[{ts}] {txt}" for ts, txt in got)
    return body, "full"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lines_by_ep, full_by_ep = load_lines()
    files = sorted(CAND_DIR.glob("batch-*.md"))

    stats = {"full": 0, "part": 0, "none": 0}
    unfixable = []
    changed_files = 0

    for f in files:
        text = f.read_text(encoding="utf-8")
        orig = text
        out_lines = []
        pos = 0
        pat = vq.QUOTE_MULTI_RE

        for m in pat.finditer(text):
            raw_q, eid = m.group(1), m.group(2)
            q = vq.clean_quote(raw_q)
            src = full_by_ep.get(eid)
            frags = vq.split_frags(q)
            if not frags:
                continue
            needs_fix = False
            if src is not None:
                hit = sum(1 for fr in frags if vq.norm(fr) in src)
                if hit < len(frags):
                    needs_fix = True
            if not needs_fix:
                continue

            new_body, status = rebuild(q, eid, lines_by_ep)
            stats[status] += 1
            if status == "none":
                unfixable.append({
                    "file": f.name, "eid": eid,
                    "quote": q[:200],
                })
                continue

            # 保留原有的 —— `eid` `[ts]` 尾巴
            tail_m = re.search(r"」 —— (`.+)$", text[m.start():m.end()], re.S)
            tail = tail_m.group(1) if tail_m else f"`{eid}`"
            new_block = f"> 「{new_body}」 —— {tail}"
            out_lines.append(text[pos:m.start()])
            out_lines.append(new_block)
            pos = m.end()

        if out_lines:
            out_lines.append(text[pos:])
            new_text = "".join(out_lines)
            if new_text != orig:
                changed_files += 1
                if not args.dry_run:
                    f.write_text(new_text, encoding="utf-8")

    print(f"扫描 {len(files)} 批")
    print(f"  可完全修复: {stats['full']}")
    print(f"  部分修复:   {stats['part']}")
    print(f"  不可修:     {stats['none']}")
    print(f"  涉及文件:   {changed_files}")
    if args.dry_run:
        print("\n[dry-run] 未写盘")

    if unfixable:
        L = ["# 引文待重读（时间戳对不上原文，必须人工回原文重找）", ""]
        L.append(f"> 生成：2026-10-31 ｜ 共 **{len(unfixable)}** 条")
        L.append("")
        L.append("这些引文的时间戳在原文里找不到对应行——说明批读者写引文时")
        L.append("**连时间戳都是凭印象给的**，不是抄的。自动修复对它们无效，")
        L.append("必须回原文按语义重找，不能用时间戳当锚。")
        L.append("")
        L.append("| 批次 | 期次 | 引文（可能整段是编的） |")
        L.append("|---|---|---|")
        for u in unfixable:
            q = u["quote"].replace("|", "｜").replace("\n", " ")
            L.append(f"| {u['file']} | `{u['eid']}` | {q[:120]} |")
        L.append("")
        L.append("> 处置：逐条回原文，找到语义对应处就重抄；确实没有的，")
        L.append("> **该条规则连带删除**（因为规则的证据不存在了）。")
        if not args.dry_run:
            OUT_UNFIXABLE.write_text("\n".join(L) + "\n", encoding="utf-8")
            print(f"\n→ {OUT_UNFIXABLE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
