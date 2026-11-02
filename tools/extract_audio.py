#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
视频抽音频 —— PyAV 实现，不依赖系统 ffmpeg。

输出 16kHz 单声道 mp3（ASR 标准输入格式，体积小、识别率不打折）。

用法:
    python extract_audio.py --input "目录或通配符" --outdir 输出目录
"""
import argparse
import glob
import os
import sys
import time

import av


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="视频文件或通配符")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--bitrate", default="64k", help="mp3 码率，16k 单声道 64k 足够")
    args = ap.parse_args()

    files = sorted(glob.glob(args.input))
    if not files:
        print(f"[ERR] no file matched: {args.input}")
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)

    for idx, path in enumerate(files, 1):
        base = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(args.outdir, base + ".mp3")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
            print(f"[{idx}/{len(files)}] SKIP (exists): {base}.mp3", flush=True)
            continue

        print(f"[{idx}/{len(files)}] {base}", flush=True)
        t0 = time.time()

        in_container = av.open(path)
        audio_streams = [s for s in in_container.streams if s.type == "audio"]
        if not audio_streams:
            print("    [WARN] no audio stream, skipped", flush=True)
            in_container.close()
            continue

        in_stream = audio_streams[0]
        out_container = av.open(out_path, mode="w", format="mp3")
        out_stream = out_container.add_stream("mp3", rate=16000, layout="mono")
        out_stream.bit_rate = 64000

        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)

        frames = 0
        for frame in in_container.decode(in_stream):
            for rf in resampler.resample(frame):
                for packet in out_stream.encode(rf):
                    out_container.mux(packet)
                frames += 1

        # flush resampler + encoder
        for rf in resampler.resample(None):
            for packet in out_stream.encode(rf):
                out_container.mux(packet)
        for packet in out_stream.encode(None):
            out_container.mux(packet)

        out_container.close()
        in_container.close()

        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(
            f"    OK -> {os.path.basename(out_path)} | {size_mb:.1f} MB | "
            f"{frames} frames | {time.time() - t0:.1f}s",
            flush=True,
        )


if __name__ == "__main__":
    main()
