#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""harvest_new_audio.py — 增量抓直链并下载（CDP 版）

历史教训（为什么最终用 CDP）：
  - headless=new：点播放后浏览器解码音频占死渲染线程，Runtime.evaluate 全超时
  - Livewire 组件调用 POST /livewire/update：419（无会话 CSRF）→ 带 cookie 后 500
    （服务端对非浏览器 playback 调用拒绝，格式/签名校验不可绕）
  - 非 headless CDP（有登录态的窗口或 about:blank 起步均可）：
    capture_one 走 snapshot 方案成功 ✅

前置：调试 Chrome 跑在 127.0.0.1:9223（非 headless）
  chrome --remote-debugging-port=9223 --user-data-dir=<本仓库>_tmp_chrome_profile
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.stdout.reconfigure(encoding="utf-8")

import earsonme_cdp_harvest as H

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"}


def main():
    check = json.loads((ROOT / "research" / "_增量体检.json").read_text(encoding="utf-8"))
    new_ids = check["new"]
    urls_path = ROOT / "sources" / "00-原始素材" / "earsonme" / "urls.json"
    data = json.loads(urls_path.read_text(encoding="utf-8")) if urls_path.exists() else {}
    todo = [e for e in new_ids if e not in data]
    print(f"目标 {len(new_ids)} 个新期，待抓 {len(todo)}")

    ws = H.attach()
    for i, eid in enumerate(todo, 1):
        url, how = None, "init"
        for attempt in range(2):
            try:
                url, how = H.capture_one(ws, eid)
                break
            except Exception as e:
                print(f"  {eid} 第 {attempt+1} 次异常: {type(e).__name__}，重建连接")
                try:
                    ws = H.attach()
                except Exception:
                    time.sleep(5)
        if url:
            data[eid] = url
            print(f"[{i}/{len(todo)}] {eid} ✓ {how}")
        else:
            print(f"[{i}/{len(todo)}] {eid} ✗ {how}")
        urls_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(2.0)

    got = {e: data[e] for e in new_ids if e in data}
    (ROOT / "research" / "_新期直链.json").write_text(
        json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n直链到手 {len(got)}/{len(new_ids)}")

    if got:
        audio_dir = ROOT / "sources" / "00-原始素材" / "earsonme" / "audio"
        audio_dir.mkdir(exist_ok=True)
        total = 0
        for eid, url in got.items():
            dest = audio_dir / f"{eid}.m4a"
            if dest.exists() and dest.stat().st_size > 100_000:
                print(f"  {eid} 已有，跳过")
                continue
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                mb = dest.stat().st_size / 1e6
                total += mb
                print(f"  {eid} {mb:.1f} MB（累计 {total:.1f} MB）")
            except Exception as e:
                print(f"  {eid} 下载失败: {e}")
        print(f"\n下载完成，本轮流量 {total:.1f} MB")


if __name__ == "__main__":
    main()
