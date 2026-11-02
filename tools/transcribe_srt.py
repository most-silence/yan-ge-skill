#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
眼哥素材转写器 v2 —— faster-whisper，输出 SRT + 纯文本双份。

崩溃教训（2026-10-21 实测）：
    beam_size=5 + vad_filter=True + temperature 列表 会触发 0xC0000005。
    可用配置：beam_size=1、vad_filter=False、不传 temperature。
    速度约 2.5x 实时（Ryzen 7 7840H, int8, 8 线程）。

用法:
    python transcribe_srt.py --input "*.mp3" --outdir 输出目录 --model small
"""
import argparse
import glob
import os
import sys
import time

# 领域提示词：修正 ASR 专有名词错误（实测把「眼哥」听成「演歌」）
DOMAIN_PROMPT = (
    "以下是一档中国A股股票节目，主播叫眼哥，节目叫眼哥股市会，平台是小宇宙和抖音，"
    "抖音账号叫一双看透真相的双眼。内容讲均线系统、做T、盯盘、大盘、指数、板块、"
    "个股、成交量、换手率、龙头、涨停、跌停、支撑位、压力位、缩量、放量、主力、游资、"
    "北向资金、沪深300、创业板、科创板、新能源、半导体、军工、消费、医药、券商。"
)

# 术语纠错表：ASR 高频误识别 -> 正确写法
FIXES = [
    ("演歌", "眼哥"),
    ("军线", "均线"),
    ("均綫", "均线"),
    ("都因", "抖音"),
    ("小宇宙", "小宇宙"),
    ("做t", "做T"),
    ("做 t", "做T"),
    ("大盘", "大盘"),
    ("北向", "北向"),
    ("护身三百", "沪深300"),
    ("创业板", "创业板"),
]


def fmt_srt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def apply_fixes(text: str) -> str:
    for wrong, right in FIXES:
        text = text.replace(wrong, right)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--model", default="small")
    ap.add_argument("--language", default="zh")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--compute-type", default="int8")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--limit-min", type=float, default=0.0)
    args = ap.parse_args()

    from faster_whisper import WhisperModel

    files = sorted(glob.glob(args.input))
    if not files:
        print(f"[ERR] no file matched: {args.input}")
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)

    print(f"[model] loading {args.model} ...", flush=True)
    t0 = time.time()
    model = WhisperModel(
        args.model, device=args.device,
        compute_type=args.compute_type, cpu_threads=args.threads,
    )
    print(f"[model] ready in {time.time() - t0:.1f}s", flush=True)

    for idx, path in enumerate(files, 1):
        base = os.path.splitext(os.path.basename(path))[0]
        srt_path = os.path.join(args.outdir, base + ".srt")
        txt_path = os.path.join(args.outdir, base + ".txt")
        if os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
            print(f"[{idx}/{len(files)}] SKIP: {base}", flush=True)
            continue

        print(f"[{idx}/{len(files)}] {base}", flush=True)
        started = time.time()

        segments, info = model.transcribe(
            path,
            language=args.language,
            beam_size=1,                 # 关键：5 会崩
            vad_filter=False,            # 关键：True 会崩
            initial_prompt=DOMAIN_PROMPT,
            condition_on_previous_text=False,
        )

        duration = info.duration
        if args.limit_min > 0:
            duration = min(duration, args.limit_min * 60)

        srt_lines, txt_lines = [], []
        n = 0
        for seg in segments:
            if seg.start > duration:
                break
            text = apply_fixes(seg.text.strip())
            if not text:
                continue
            n += 1
            srt_lines.append(f"{n}\n{fmt_srt_ts(seg.start)} --> {fmt_srt_ts(seg.end)}\n{text}\n")
            txt_lines.append(f"[{fmt_ts(seg.start)}] {text}")
            if n % 100 == 0:
                print(f"    ... {fmt_ts(seg.end)} / {fmt_ts(duration)}", flush=True)

        with open(srt_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(srt_lines))

        header = (
            f"# 元信息\n"
            f"来源音频：{os.path.basename(path)}\n"
            f"音频时长：{fmt_ts(duration)}\n"
            f"转写工具：faster-whisper {args.model} ({args.compute_type})\n"
            f"转写时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"说话人：眼哥（未做说话人分离）\n"
            f"---\n\n"
        )
        with open(txt_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(header + "\n".join(txt_lines) + "\n")

        elapsed = time.time() - started
        print(
            f"    OK | {n} segs | {elapsed / 60:.1f} min | "
            f"{duration / elapsed:.1f}x realtime",
            flush=True,
        )

    print(f"[done] {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
