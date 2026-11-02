"""download_audio.py — 批量下载 earsonme 音频直链。

- 读 urls.json（eid → m4a 直链），下载到 sources/00-原始素材/earsonme/audio/
- 文件名：YYYY-MM-DD_eid_标题.m4a（日期/标题来自 全量清单.json，缺失则用 eid）
- 断点续传：已有文件按字节数续传（xyzcdn 支持 Range）；大小对上 Content-Length 即跳过
- 可与直链抓取并行运行（urls.json 增量写盘，每轮重新读取）

用法：python download_audio.py [--loop]   # --loop 持续轮询新直链直到 364 全齐
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(r"E:\AIProjetct\Nothing\眼哥\sources\00-原始素材\earsonme")
URLS = BASE / "urls.json"
ROWS = BASE / "全量清单.json"
DEST = BASE / "audio"
DEST.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0"}
GOOD = re.compile(r"^https://media\.xyzcdn\.net/[A-Za-z0-9_\-]+/[A-Za-z0-9_\-]+\.m4a$")


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]', "_", s).strip()


def filename_for(eid, meta):
    d = (meta or {}).get("rel") or ""
    title = safe_name((meta or {}).get("short") or eid)[:60]
    return f"{eid}_{title}.m4a"


def head_size(url):
    req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        cr = r.headers.get("Content-Range", "")
        if "/" in cr:
            return int(cr.split("/")[-1])
        return int(r.headers.get("Content-Length") or 0)


def download(url, path):
    """流式下载，断点续传，返回 (状态, 字节数)。"""
    have = path.stat().st_size if path.exists() else 0
    try:
        total = head_size(url)
    except Exception as e:
        return f"head-fail:{type(e).__name__}", have
    if have and total and have == total:
        return "exists", have

    headers = dict(UA)
    if have:
        headers["Range"] = f"bytes={have}-"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(path, "ab" if have else "wb") as f:
            got = have
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
        return "ok" if not total or got == total else f"short:{got}/{total}", got
    except Exception as e:
        return f"dl-fail:{type(e).__name__}", path.stat().st_size if path.exists() else 0


def one_pass(rows_meta, quiet=False):
    urls = load(URLS, {})
    done = load(BASE / "download_state.json", {})
    n_ok = n_skip = 0
    for eid, url in urls.items():
        if not GOOD.match(url):
            continue
        if done.get(eid) == "ok":
            n_skip += 1
            continue
        path = DEST / filename_for(eid, rows_meta.get(eid))
        status, size = download(url, path)
        if status in ("ok", "exists"):
            done[eid] = "ok"
            n_ok += 1
            if not quiet and status == "ok":
                print(f"  ↓ {eid} {size/1e6:.1f}MB {path.name[:40]}", flush=True)
        else:
            if not quiet:
                print(f"  ✗ {eid} {status}", flush=True)
        done[f"_ts_{eid}"] = status
    (BASE / "download_state.json").write_text(
        json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(urls), n_skip, n_ok


def main():
    rows = load(ROWS, [])
    rows_meta = {r["eid"]: r for r in rows}
    loop = "--loop" in sys.argv
    while True:
        total, n_skip, n_ok = one_pass(rows_meta)
        n_done = n_skip + 0
        print(f"== 本轮：直链 {total}，已完成 {n_skip}，新下载 {n_ok}", flush=True)
        if not loop or (total and n_skip >= total):
            print("全部下载完成" if n_skip >= total else "urls.json 未齐，退出（用 --loop 重跑）", flush=True)
            break
        time.sleep(60)


if __name__ == "__main__":
    main()
