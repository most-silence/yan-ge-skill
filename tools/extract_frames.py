#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
关键帧抽取 —— 把转写稿里的「这个位置」「这条线」锚定到具体画面。

策略：
  1. 按转写稿时间戳，在「指代密集」的句子附近抽帧
  2. 抽帧时刻 = 句子开始时间 + 1.5 秒（留出画面切换时间）
  3. 输出 jpg + 一份 manifest.csv（帧号 / 时间戳 / 对应原话）

用法:
    python extract_frames.py --video x.mp4 --transcript x.txt --outdir frames/
"""
import argparse
import csv
import os
import re
import sys

import av


# 指代词：出现这些词就说明他在指画面
DEICTIC = [
    "这个位置", "这个地方", "这条线", "这个图", "这个图形", "这里", "这边",
    "这根", "这个点", "上面", "下面", "左边", "右边", "前面", "后面",
    "这个票", "这根线", "那个位置", "这条", "这个指标", "看到没有", "看见没有",
]


def parse_transcript(path):
    """解析 [HH:MM:SS] 文本 格式"""
    out = []
    pat = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]\s*(.*)$")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.strip())
            if m:
                h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
                out.append((h * 3600 + mi * 60 + s, m.group(4).strip()))
    return out


def pick_moments(entries, gap_seconds=8.0, lead=1.5):
    """
    挑出需要截图的时刻。
    - 只在含指代词的句子处截
    - 相邻两帧至少间隔 gap_seconds，避免同一画面重复截
    """
    picked = []
    last_t = -999
    for t, text in entries:
        if not any(d in text for d in DEICTIC):
            continue
        shot = t + lead
        if shot - last_t < gap_seconds:
            continue
        picked.append((shot, text))
        last_t = shot
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--gap", type=float, default=8.0)
    ap.add_argument("--max", type=int, default=0, help="最多抽多少帧，0=不限")
    args = ap.parse_args()

    entries = parse_transcript(args.transcript)
    if not entries:
        print("[ERR] transcript parsed 0 lines")
        sys.exit(1)

    moments = pick_moments(entries, gap_seconds=args.gap)
    if args.max > 0:
        moments = moments[: args.max]

    os.makedirs(args.outdir, exist_ok=True)
    print(f"[plan] {len(entries)} lines -> {len(moments)} frames to capture", flush=True)

    container = av.open(args.video)
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"

    manifest = []
    mi = 0
    captured = 0
    targets = [(i, t, txt) for i, (t, txt) in enumerate(moments)]

    for frame in container.decode(stream):
        if frame.time is None:
            continue
        t = frame.time
        while mi < len(targets) and t >= targets[mi][1]:
            idx, shot_t, text = targets[mi]
            name = f"{idx + 1:03d}_{int(shot_t) // 60:02d}m{int(shot_t) % 60:02d}s.jpg"
            path = os.path.join(args.outdir, name)
            img = frame.to_image()
            img.save(path, quality=85)
            manifest.append({
                "frame": name,
                "time": f"{int(shot_t) // 3600:02d}:{(int(shot_t) % 3600) // 60:02d}:{int(shot_t) % 60:02d}",
                "seconds": round(shot_t, 1),
                "utterance": text,
            })
            captured += 1
            mi += 1
            if captured % 20 == 0:
                print(f"    ... {captured}/{len(targets)}", flush=True)
        if mi >= len(targets):
            break

    container.close()

    csv_path = os.path.join(args.outdir, "_manifest.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["frame", "time", "seconds", "utterance"])
        w.writeheader()
        w.writerows(manifest)

    print(f"[done] captured {captured} frames -> {args.outdir}", flush=True)
    print(f"       manifest: {csv_path}", flush=True)


if __name__ == "__main__":
    main()
