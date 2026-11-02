"""批量抓 earsonme 单集音频直链。

流程（每集约 10-14 秒）：
  1. CDP 导航到 https://earsonme.com/episodes/{eid}
  2. 从「播放」按钮的 x-on:click 里取内部 episode id
  3. 派发 play-episode 事件 → 播放器组件把该集追加进 playlist
  4. 轮询 player.snapshot.data.playlist，按内部 id 命中后读 media_url
  5. 增量写 urls.json（eid → m4a 直链），失败写 fails.json

断点续传：已在 urls.json 里的 eid 直接跳过。
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from earsonme_cdp_harvest import attach  # noqa: E402

BASE = Path(r"E:\AIProjetct\Nothing\眼哥\sources\00-原始素材\earsonme")
URLS = BASE / "urls.json"
FAILS = BASE / "fails.json"
ROWS = BASE / "全量清单.json"

JS_PREP = r"""
(()=>{
  const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='播放');
  if(!b) return JSON.stringify({err:'nobtn'});
  const m=(b.getAttribute('x-on:click')||'').match(/(\d{4,})/);
  if(!m) return JSON.stringify({err:'noid'});
  window.__iid = m[1];
  const c=window.Livewire.all().filter(x=>x.name==='player')[0];
  if(!c) return JSON.stringify({err:'noplayer'});
  window.dispatchEvent(new CustomEvent('play-episode',{detail:Number(window.__iid)}));
  return JSON.stringify({ok:1, iid:window.__iid});
})()
"""

JS_POLL = r"""
(()=>{
  const c=window.Livewire.all().filter(x=>x.name==='player')[0];
  if(!c) return JSON.stringify({err:'noplayer'});
  const pl=c.snapshot.data.playlist[0].map(x=>x[0]);
  const h=pl.find(e=>String(e.id)===String(window.__iid));
  return JSON.stringify({n:pl.length, u: h? h.media_url : null, t: h? h.title : null, d: h? h.duration : null});
})()
"""

GOOD = re.compile(r"^https://media\.xyzcdn\.net/[A-Za-z0-9_\-]+/[A-Za-z0-9_\-]+\.m4a$")


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def save(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def capture(ws, eid, poll_max=14.0):
    ws.call("Page.navigate", url=f"https://earsonme.com/episodes/{eid}")
    deadline = time.time() + 12
    prep = None
    while time.time() < deadline:
        time.sleep(1.2)
        try:
            raw = ws.eval_js(JS_PREP)
        except Exception:
            continue
        if raw:
            prep = json.loads(raw)
            if prep.get("ok"):
                break
            if prep.get("err") == "noid":
                return None, "no-internal-id"
    if not prep or not prep.get("ok"):
        return None, (prep or {}).get("err", "prep-failed")

    end = time.time() + poll_max
    while time.time() < end:
        time.sleep(1.5)
        raw = ws.eval_js(JS_POLL)
        if not raw:
            continue
        j = json.loads(raw)
        u = j.get("u")
        if u and GOOD.match(u):
            return u, "ok"
        if u:
            return None, f"bad-url:{u[:60]}"
    return None, "poll-timeout"


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    rows = load(ROWS, [])
    if not rows:
        print("缺 全量清单.json")
        return
    ids = [r["eid"] for r in rows]
    urls = load(URLS, {})
    # 清掉历史误捕的图片地址
    bad = [k for k, v in urls.items() if not GOOD.match(v)]
    for k in bad:
        del urls[k]
    fails = load(FAILS, {})
    todo = [e for e in ids if e not in urls]
    if limit:
        todo = todo[:limit]
    print(f"总 {len(ids)} 集，已有直链 {len(urls)}，本轮待抓 {len(todo)}", flush=True)

    ws = attach()
    t0 = time.time()
    for n, eid in enumerate(todo, 1):
        url, why = capture(ws, eid)
        if url:
            urls[eid] = url
            fails.pop(eid, None)
            print(f"[{n}/{len(todo)}] {eid} ✓ …{url[-28:]}", flush=True)
        else:
            fails[eid] = why
            print(f"[{n}/{len(todo)}] {eid} ✗ {why}", flush=True)
        save(URLS, urls)
        save(FAILS, fails)
        if n % 20 == 0:
            el = time.time() - t0
            print(f"--- 进度 {n}/{len(todo)}，累计 {len(urls)} 条，"
                  f"{(el / n):.1f}s/集，预计还需 {(len(todo) - n) * el / n / 60:.0f} 分钟", flush=True)
        time.sleep(1.5)
    print(f"结束：直链 {len(urls)} / {len(ids)}，失败 {len(fails)}", flush=True)


if __name__ == "__main__":
    main()
