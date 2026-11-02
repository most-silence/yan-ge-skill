#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PDF 文本提取 —— 纯 Python（pypdf），不依赖 PyMuPDF（本机崩溃 0xC0000005）。

先做体检：判断每本书是「文字版」还是「扫描版」。
扫描版需要 OCR，文字版直接提取。

用法:
    python extract_pdf.py --input "目录/*.pdf" --outdir 输出目录
    python extract_pdf.py --input "x.pdf" --probe      # 只体检不提取
"""
import argparse
import glob
import os
import sys
import time

from pypdf import PdfReader


def probe(path, sample_pages=10):
    """体检：返回 (总页数, 抽样字符数, 是否文字版)"""
    reader = PdfReader(path)
    total = len(reader.pages)
    n = min(sample_pages, total)
    chars = 0
    for i in range(n):
        try:
            t = reader.pages[i].extract_text() or ""
            chars += len(t.strip())
        except Exception:
            pass
    per_page = chars / n if n else 0
    return total, per_page


def extract(path, out_path):
    reader = PdfReader(path)
    total = len(reader.pages)
    parts = []
    empty = 0
    for i, page in enumerate(reader.pages, 1):
        try:
            t = (page.extract_text() or "").strip()
        except Exception as e:
            t = ""
        if not t:
            empty += 1
        parts.append(f"\n\n<!-- page {i} -->\n{t}")
        if i % 50 == 0:
            print(f"    ... {i}/{total}", flush=True)

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts))
    return total, empty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", default="")
    ap.add_argument("--probe", action="store_true", help="只体检")
    ap.add_argument("--min-chars", type=int, default=100,
                    help="每页平均字符数低于此值判定为扫描版")
    args = ap.parse_args()

    files = sorted(glob.glob(args.input))
    if not files:
        print(f"[ERR] no file matched: {args.input}")
        sys.exit(1)

    print(f"{'文件':<44} {'页数':>6} {'字符/页':>9}  判定")
    print("-" * 78)

    results = []
    for path in files:
        base = os.path.splitext(os.path.basename(path))[0]
        try:
            total, per_page = probe(path)
        except Exception as e:
            print(f"{base[:42]:<44} {'?':>6} {'?':>9}  ❌ {type(e).__name__}: {e}")
            continue
        is_text = per_page >= args.min_chars
        tag = "✅ 文字版" if is_text else "⚠️ 扫描版（需 OCR）"
        print(f"{base[:42]:<44} {total:>6} {per_page:>9.0f}  {tag}")
        results.append((path, base, total, per_page, is_text))

    if args.probe:
        return

    os.makedirs(args.outdir, exist_ok=True)
    print()
    for path, base, total, per_page, is_text in results:
        if not is_text:
            print(f"[SKIP] {base} —— 扫描版，跳过（需先 OCR）")
            continue
        out_path = os.path.join(args.outdir, base + ".txt")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            print(f"[SKIP] {base} —— 已存在")
            continue
        print(f"[{base}] 提取中 ({total} 页)...", flush=True)
        t0 = time.time()
        n, empty = extract(path, out_path)
        size = os.path.getsize(out_path)
        print(f"    OK | {size/1024:.0f} KB | 空页 {empty}/{n} | {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
