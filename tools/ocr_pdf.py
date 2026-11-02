#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
扫描版 PDF OCR —— PyMuPDF 渲染 + RapidOCR 识别，纯 CPU，不依赖 torch。

环境要求（本机实测）：
    onnxruntime==1.19.2   ← ⚠️ 1.31.0 会崩 0xC0000005，必须降级
    pymupdf>=2.0
    rapidocr-onnxruntime

用法:
    python ocr_pdf.py --pdf "x.pdf" --outdir 输出目录 --dpi 200
    python ocr_pdf.py --pdf "x.pdf" --start 1 --end 10      # 先试 10 页
"""
import argparse
import os
import sys
import time

import pymupdf
from rapidocr_onnxruntime import RapidOCR


def ocr_pdf(pdf_path, out_path, dpi=200, start=1, end=None, resume=True):
    doc = pymupdf.open(pdf_path)
    total = len(doc)
    end = min(end or total, total)
    engine = RapidOCR()

    # 断点续跑：已有部分结果就接着写
    done = 0
    if resume and os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            done = sum(1 for line in f if line.startswith("<!-- page "))
        if done > 0:
            print(f"    续跑：已完成 {done} 页", flush=True)

    mode = "a" if done > 0 else "w"
    f = open(out_path, mode, encoding="utf-8", newline="\n")

    try:
        for i in range(start - 1, end):
            page_no = i + 1
            if page_no <= done:
                continue
            t0 = time.time()
            page = doc[i]
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")

            result, _ = engine(img_bytes)
            if result:
                # result = [[box, text, score], ...]
                lines = [item[1] for item in result if item[2] > 0.5]
                text = "\n".join(lines)
            else:
                text = ""

            f.write(f"\n\n<!-- page {page_no} -->\n{text}")
            f.flush()
            print(f"    p{page_no}/{end} | {len(text):>4} 字 | {time.time()-t0:.1f}s", flush=True)
    finally:
        f.close()
        doc.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=0)
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()

    base = os.path.splitext(os.path.basename(args.pdf))[0]
    os.makedirs(args.outdir, exist_ok=True)
    out_path = os.path.join(args.outdir, base + ".txt")

    print(f"[OCR] {base}", flush=True)
    t0 = time.time()
    ocr_pdf(
        args.pdf, out_path,
        dpi=args.dpi, start=args.start,
        end=args.end or None,
        resume=not args.no_resume,
    )
    size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
    print(f"[done] {size/1024:.0f} KB | {time.time()-t0:.0f}s -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
