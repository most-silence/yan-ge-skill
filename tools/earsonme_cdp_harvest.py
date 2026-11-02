#!/usr/bin/env python3
"""earsonme_cdp_harvest.py v2 — 登录态 CDP 全量收割（ID 清单 + 音频直链）。

前置：msedge --remote-debugging-port=9223 --user-data-dir=%LOCALAPPDATA%\\Temp\\edge-cdp-earsonme
      并在该窗口登录 earsonme.com（用户手动一次）。

用法:
  python earsonme_cdp_harvest.py --ids          # 登录态翻页收全 364 个 eid
  python earsonme_cdp_harvest.py --audio        # 逐集点播放抓 audio.src，增量写 urls.json
  python earsonme_cdp_harvest.py --audio --limit 3
断点续传：urls.json 已有的 eid 自动跳过。
"""
import argparse
import base64
import json
import os
import re
import socket
import struct
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PODCAST_PATH = "/podcasts/IQpid2Xv/episodes"
EID_RE = re.compile(r"/episodes/([A-Za-z0-9]{12})")
CURSOR_RE = re.compile(r'href="(/podcasts/IQpid2Xv/episodes\?cursor=[^"]+)"')
DEBUG_HOST = "http://127.0.0.1:9223"
OUT = Path(__file__).resolve().parent.parent / "sources" / "00-原始素材" / "earsonme"


def _urandom(n):
    return os.urandom(n)


class Tab:
    """最小 CDP over WebSocket 客户端（标准库，无三方依赖）。"""

    def __init__(self, ws_url):
        p = urllib.parse.urlparse(ws_url)
        self.sock = socket.create_connection((p.hostname, p.port), timeout=15)
        key = base64.b64encode(b"0123456789abcdef").decode()
        path = p.path + (f"?{p.query}" if p.query else "")
        self.sock.sendall(
            (
                f"GET {path} HTTP/1.1\r\nHost: {p.hostname}:{p.port}\r\n"
                f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("ws handshake closed")
            buf += chunk
        self._buf = buf.split(b"\r\n\r\n", 1)[1]
        self._id = 0

    def _read_frame(self):
        def rd(n):
            while len(self._buf) < n:
                c = self.sock.recv(max(4096, n - len(self._buf)))
                if not c:
                    raise ConnectionError("ws closed")
                self._buf += c
            out, self._buf = self._buf[:n], self._buf[n:]
            return out

        hdr = rd(2)
        ln = hdr[1] & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", rd(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", rd(8))[0]
        return rd(ln)

    def recv_message(self, timeout=1.0):
        self.sock.settimeout(timeout)
        try:
            payload = self._read_frame()
        except (TimeoutError, socket.timeout):
            return None
        try:
            return json.loads(payload.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            return None
        finally:
            self.sock.settimeout(15)

    def call(self, method, **params):
        self._id += 1
        mid = self._id
        data = json.dumps({"id": mid, "method": method, "params": params}).encode()
        mask = _urandom(4)
        frame = bytearray([0x81])
        n = len(data)
        if n < 126:
            frame.append(0x80 | n)
        elif n < 65536:
            frame.append(0x80 | 126)
            frame += struct.pack(">H", n)
        else:
            frame.append(0x80 | 127)
            frame += struct.pack(">Q", n)
        frame += mask
        frame += bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(frame)
        deadline = time.time() + (300 if method == "Runtime.evaluate" else 30)
        while time.time() < deadline:
            m = self.recv_message(2.0)
            if m and m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m
        raise TimeoutError(f"CDP call timeout: {method}")

    def drain(self, seconds):
        end = time.time() + seconds
        out = []
        while time.time() < end:
            m = self.recv_message(0.4)
            if m:
                out.append(m)
        return out

    def eval_js(self, expr, await_promise=False):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True,
                      awaitPromise=await_promise)
        res = r.get("result", {}).get("result", {})
        return res.get("value")


def get_targets():
    with urllib.request.urlopen(f"{DEBUG_HOST}/json/list", timeout=5) as r:
        return json.load(r)


def attach():
    tabs = [t for t in get_targets() if t.get("type") == "page"]
    if not tabs:
        sys.exit("9223 上没有 page target")
    ws = Tab(tabs[0]["webSocketDebuggerUrl"])
    ws.call("Page.enable")
    ws.call("Network.enable")
    return ws


def ensure_site(ws):
    cur = [t for t in get_targets() if t.get("type") == "page"][0]["url"]
    if "earsonme.com" not in cur:
        ws.call("Page.navigate", url="https://earsonme.com" + PODCAST_PATH)
        time.sleep(5)
    # 登录检查：有「退出/个人中心」即已登录（页面右上角永远渲染一个「登录」链接文案）
    for attempt in range(3):
        logged_in = ws.eval_js(
            "document.body.textContent.includes('退出') || document.body.textContent.includes('个人中心')"
        )
        if logged_in:
            break
        time.sleep(5)
    if not logged_in:
        print("⚠ 未检测到登录态。请在 CDP 窗口登录 earsonme.com 后重跑。")
        ws.call("Page.navigate", url="https://earsonme.com/login")
        sys.exit(1)


def harvest_ids(ws):
    """登录态在页面内 fetch 翻全部 cursor 页，收全 eid。"""
    ws.call("Page.navigate", url="https://earsonme.com" + PODCAST_PATH)
    time.sleep(5)
    js = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const ids = new Set();
  let next = %PODCAST%;
  for (let guard = 0; guard < 80 && next; guard++) {
    const html = await fetch(next, {credentials:'include'}).then(r => r.text());
    for (const m of html.matchAll(/\/episodes\/([A-Za-z0-9]{12})/g)) ids.add(m[1]);
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const nx = [...doc.querySelectorAll('a')].find(a => /下一页/.test(a.textContent));
    next = nx ? nx.getAttribute('href') : null;
    if (next && next.startsWith('/')) next = new URL(next, location.origin).pathname + next.slice(next.indexOf('?'));
    await sleep(700);
  }
  return JSON.stringify([...ids]);
})()
""".replace("%PODCAST%", json.dumps(PODCAST_PATH))
    raw = ws.eval_js(js, await_promise=True)
    ids = json.loads(raw)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_earsonme_ids.json").write_text(json.dumps(ids, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"共 {len(ids)} 集 → {OUT/'_earsonme_ids.json'}")
    return ids


JS_CLICK_PLAY = """(() => {
  const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === '播放');
  if (b) { b.click(); return 'ok'; }
  return document.querySelector('audio') ? 'already' : 'notfound';
})()"""

# 点播放后直接从播放列表快照读 media_url —— 不用等 audio.src（点击后
# audio 标签可能延迟出现，但快照 2 秒内就有 URL）。
JS_SNAPSHOT_URL = """(() => {
  const iid = window.__iid;
  const c = window.Livewire && window.Livewire.all().find(x => x.name === 'player');
  if (!c || !iid) return '';
  const pl = c.snapshot.data.playlist[0];
  const hit = pl.find(e => String(e[0].id) === String(iid));
  return hit && hit[0].media_url ? hit[0].media_url : '';
})()"""

# 从播放按钮的 x-on:click 属性提取该集的条目 id（数字 iid，非 12 位 eid）
JS_GET_IID = """(() => {
  const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim() === '播放');
  if (!b) return '';
  const m = (b.getAttribute('x-on:click') || '').match(/(\\d+)/);
  return m ? m[1] : '';
})()"""


def capture_one(ws, eid, wait=14.0, retries=4):
    """打开单集页 → 点播放 → 从播放列表快照读 media_url；返回直链或 None。

    源站偶发 Cloudflare 522（过载）：遇 522/无播放按钮则指数退避重试。
    """
    delay = 6.0
    for attempt in range(retries):
        ws.call("Page.navigate", url=f"https://earsonme.com/episodes/{eid}")
        time.sleep(4)
        title = ws.eval_js("document.title") or ""
        if "522" in title or "Connection timed out" in title:
            print(f"    522 过载，退避 {delay:.0f}s（第 {attempt + 1} 次）")
            time.sleep(delay)
            delay = min(delay * 1.7, 60)
            continue
        iid = ws.eval_js(JS_GET_IID)
        if not iid:
            time.sleep(delay)
            delay = min(delay * 1.7, 60)
            continue
        ws.eval_js("window.__iid = %s; 'ok'" % json.dumps(iid))
        ws.eval_js(JS_CLICK_PLAY)
        end = time.time() + wait
        while time.time() < end:
            time.sleep(1.5)
            u = ws.eval_js(JS_SNAPSHOT_URL) or ""
            if "media.xyzcdn.net" in u and "@thumbnail" not in u:
                return u, "snapshot"
        time.sleep(delay)
        delay = min(delay * 1.7, 60)
    return None, "retries-exhausted"


def harvest_audio(ws, ids, limit=0):
    urls_path = OUT / "urls.json"
    data = {}
    if urls_path.exists():
        data = json.loads(urls_path.read_text(encoding="utf-8"))
        print(f"断点续传：已有 {len(data)} 条直链")
    todo = [e for e in ids if e not in data]
    if limit:
        todo = todo[:limit]
    fails = {}
    for i, eid in enumerate(todo, 1):
        url, how = capture_one(ws, eid)
        if url:
            data[eid] = url
            print(f"[{i}/{len(todo)}] {eid} ✓ {how} {url[:80]}")
        else:
            fails[eid] = how
            print(f"[{i}/{len(todo)}] {eid} ✗ {how}")
        urls_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(2.5)
    (OUT / "fails.json").write_text(json.dumps(fails, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n直链总数 {len(data)}，本轮失败 {len(fails)}（详见 fails.json）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", action="store_true")
    ap.add_argument("--audio", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if not (a.ids or a.audio):
        ap.error("选 --ids 或 --audio")
    ws = attach()
    ensure_site(ws)
    if a.ids:
        harvest_ids(ws)
        return
    ids_path = OUT / "_earsonme_ids.json"
    if not ids_path.exists():
        print("先跑 --ids")
        return
    harvest_audio(ws, json.loads(ids_path.read_text(encoding="utf-8")), a.limit)


if __name__ == "__main__":
    main()
