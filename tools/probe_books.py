# -*- coding: utf-8 -*-
"""书籍结构探查：章节、页数、关键词分布。"""
import re, os, sys, collections

BASE = r"E:\AIProjetct\Nothing\眼哥\books\00-原始"

BOOKS = [
    "《笑傲牛熊》史丹•温斯坦.txt",
    "股票魔法师.txt",
    "手把手教你读财报－唐朝.txt",
    "【股市操练大全4(第四册)】.txt",
]

CH_PAT = re.compile(r"^(第[一二三四五六七八九十百零]+[章节篇部]|Chapter\s*\d+|CHAPTER\s*\d+)\s*\S*")


def probe(fn):
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        print(f"\n!! 缺失: {fn}")
        return
    t = open(p, encoding="utf-8", errors="ignore").read()
    lines = [l.strip() for l in t.split("\n")]
    nonempty = [l for l in lines if l]
    print("=" * 70)
    print(f"{fn}")
    print(f"  {len(t):,} 字符 | {len(lines):,} 行 | 非空 {len(nonempty):,}")
    ch = [l for l in nonempty if CH_PAT.match(l) and len(l) < 45]
    print(f"  章节标题 {len(ch)} 个：")
    for c in ch[:50]:
        print("     ", c)
    if len(ch) > 50:
        print(f"      ... 还有 {len(ch)-50} 个")


for fn in BOOKS:
    probe(fn)
