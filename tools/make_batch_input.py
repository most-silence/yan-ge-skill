#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""make_batch_input.py — 从清洗稿生成批读输入（增量批通用）

用法：python tools/make_batch_input.py <起始批号> <oid1> <oid2> ...
     或 python tools/make_batch_input.py 99 --from-manifest

增量批特点：
- 期次 ID 用官方 24 位 oid（与历史 12 位短 eid 是两套编码，互不冲突）
- 日期从 _官方最新15期.json（oid 前 8 位 hex = 发布时间戳）取
- 行情阶段从 _行情阶段.md 按日期定档，取不到则按大盘数据判 R8 延续
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

AUDIO = ROOT / "sources" / "05-播客转写" / "audio_txt"
OFFICIAL = ROOT / "research" / "_官方最新15期.json"
MANIFEST = ROOT / "research" / "_新期manifest.json"
REGIME_MD = ROOT / "sources" / "05-播客转写" / "_行情阶段.md"


def load_official():
    """oid → {title, date}"""
    if OFFICIAL.exists():
        d = json.loads(OFFICIAL.read_text(encoding="utf-8"))
        return {x["oid"]: x for x in d}
    return {}


def find_clean(oid):
    hits = list(AUDIO.glob(f"{oid}*._clean.txt"))
    return hits[0] if hits else None


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: make_batch_input.py <批号> [--from-manifest | oid...]")
        return 1
    bno = int(args[0])
    off = load_official()

    if len(args) > 1 and args[1] == "--from-manifest":
        oids = [x["oid"] for x in json.loads(MANIFEST.read_text(encoding="utf-8"))]
    else:
        oids = args[1:]

    # 按日期排序
    def date_of(oid):
        return off.get(oid, {}).get("date", "9999")
    oids.sort(key=date_of)

    L = []
    A = L.append
    d0, d1 = date_of(oids[0]), date_of(oids[-1])
    A(f"# 批读批次 {bno}（增量补录）")
    A("")
    A(f"> 本期数：**{len(oids)}** ｜ 行情阶段：**R8 再下跌延续（低位震荡）** ｜ 日期跨度：{d0} ~ {d1}")
    A("> 增量补录：官方小宇宙源发现的新发布期次（earsonme 镜像滞后，已改用官方源）")
    A("> ⚠️ 全批 R8 同阶段——「跨阶段」栏照实写单阶段，不要硬凑")
    A("> 期次 ID 用官方 24 位 oid（历史 12 位短 eid 是另一套编码，勿混淆）")
    A("")
    A("> **给批读员的提醒（重要）**：下面「背景」栏只是行情数据事实，"
      "**不是要你去找某个特定点位或某条判断链**。"
      "请以正文实际说了什么为准——背景里提到的点位/事件，"
      "正文若没提，就照实不产卡，更不要为了接续某条链而编造表述。"
      "发现背景与正文不符，请在产出里明确上报。")
    A("")
    # 中性背景：只给可核验的行情事实，不预设「他一定在盯某个关口」
    A("## 背景（行情数据事实，非解读指引）")
    A("")
    A(f"> 上证区间收盘 {d0}~{d1}：见 research/大盘数据.json；本批各期正文"
      "实际谈到哪些点位，以正文为准。")
    A("")
    A("")
    A("---")
    A("")

    n_ok = 0
    for i, oid in enumerate(oids, 1):
        f = find_clean(oid)
        if not f:
            A(f"## {i}. {off.get(oid,{}).get('title',oid)}（`{oid}`）")
            A("")
            A("> ⚠️ 清洗稿缺失，跳过")
            A("")
            continue
        n_ok += 1
        meta = off.get(oid, {})
        title = meta.get("title", oid)
        date = meta.get("date", "无日期")
        dur = meta.get("duration", 0)
        A(f"## {i}. {title}")
        A("")
        A("| 项 | 值 |")
        A("|---|---|")
        A(f"| 期次 ID | `{oid}` |")
        A(f"| 发布日期 | {date} |")
        A("| 行情阶段 | **R8 再下跌** |")
        if dur:
            A(f"| 音频时长 | {dur//60} 分钟 |")
        A("")
        A("### 正文")
        A("")
        A(f.read_text(encoding="utf-8"))
        A("")
        A("---")
        A("")

    out = ROOT / f"sources/05-播客转写/_batches/batch-{bno}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"batch-{bno}.md: {out.stat().st_size/1024:.0f} KB, {n_ok}/{len(oids)} 期有清洗稿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
