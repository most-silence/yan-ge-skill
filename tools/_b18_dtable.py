import re
from pathlib import Path

ROOT = Path(r"E:\AIProjetct\Nothing\眼哥")
d = ROOT / "sources/05-播客转写/audio_txt"
F = {
    "xXbq00mp4j8C": "xXbq00mp4j8C_眼哥股市会 5月18日._clean.txt",
    "A8RQb9NRe5Zs": "A8RQb9NRe5Zs_眼哥股市会 8月12日._clean.txt",
    "9BJToFj5QFAr": "9BJToFj5QFAr_眼哥股市会 9月10日._clean.txt",
    "pEzd4aIgCMlt": "pEzd4aIgCMlt_说在8月开盘前._clean.txt",
}
NOISE = {
    "xXbq00mp4j8C": [("00:00:00", "00:04:36"), ("00:12:16", "00:12:46"), ("00:16:56", "00:17:27")],
    "A8RQb9NRe5Zs": [("00:00:00", "00:00:33"), ("00:03:35", "00:07:39"), ("00:17:35", "00:19:30"), ("00:19:31", "00:19:56")],
    "9BJToFj5QFAr": [("00:00:00", "00:01:00"), ("00:08:19", "00:16:00")],
    "pEzd4aIgCMlt": [("00:00:00", "00:07:45"), ("00:08:28", "00:11:52")],
}
# 归类标签：按子区间起点映射
LABELS = {
    ("xXbq00mp4j8C", 0): "开场寒暄、生日祝福、阿云节目评论区回应、节目定位、对谈预告",
    ("xXbq00mp4j8C", 720): "板块口播被打断（自述「我们才说不不说板块的」）",
    ("xXbq00mp4j8C", 1016): "收尾致意",
    ("A8RQb9NRe5Zs", 0): "片头",
    ("A8RQb9NRe5Zs", 215): "红色火箭 App 推广与注册说明",
    ("A8RQb9NRe5Zs", 1055): "个股即时闲聊（智障、肥哥、存储、人妻弦、自驾）",
    ("9BJToFj5QFAr", 0): "教师节致辞",
    ("9BJToFj5QFAr", 499): "答听众（光纤/割肉/怎么操作）、外盘叙述、反问立场",
    ("pEzd4aIgCMlt", 0): "周末生活、旅行回忆、人生幻想",
    ("pEzd4aIgCMlt", 508): "情绪抒发、留与走",
}


def i(x):
    h, m, s = map(int, x.split(":"))
    return h * 3600 + m * 60 + s


def j(t):
    return f"{t//3600:02d}:{t%3600//60:02d}:{t%60:02d}"


md = (ROOT / "sources/05-播客转写/_规则候选/batch-18.md").read_text(encoding="utf-8")
QW = re.compile(r"—— `([A-Za-z0-9]+)` `\[(\d\d:\d\d:\d\d)\]`~`\[(\d\d:\d\d:\d\d)\]`")
qw = {}
for m in QW.finditer(md):
    qw.setdefault(m.group(1), []).append((i(m.group(2)), i(m.group(3))))

GN = GT = 0
lines = []
for eid, fn in F.items():
    rows = []
    for ln in (d / fn).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\[(\d\d:\d\d:\d\d)\] (.*)$", ln)
        if m:
            rows.append((i(m.group(1)), m.group(2)))
    total = sum(len(x[1]) for x in rows)
    GT += total
    keep = set()
    for a, b in NOISE[eid]:
        keep |= set(range(i(a), i(b)))
    for a, b in qw.get(eid, []):
        keep -= set(range(a, b + 1))

    # 连续段
    runs, cur = [], None
    for s in sorted(keep):
        if cur and s == cur[1] + 1:
            cur[1] = s
        else:
            if cur:
                runs.append(cur)
            cur = [s, s]
    if cur:
        runs.append(cur)

    eid_n = 0
    # 按原始噪音块分组，便于归到 LABELS
    for a0, b0 in NOISE[eid]:
        seg_runs = [(a, b) for a, b in runs if b >= i(a0) and a < i(b0)]
        if not seg_runs:
            continue
        # 合并该块内相邻段（块内不同段共享同一标签）
        chars = 0
        for a, b in seg_runs:
            chars += sum(len(tx) for ts, tx in rows if a <= ts <= b)
        label = LABELS.get((eid, i(a0)))
        if label is None:
            label = [v for (e, s), v in LABELS.items() if e == eid and s <= i(a0)][-1]
        rng = "、".join(f"{j(a)}–{j(b)}" for a, b in seg_runs)
        eid_n += chars
        lines.append((eid, label, rng, chars))
        print(f"{eid} {label[:20]:22s} {rng}  {chars}")
    GN += eid_n
    print(f"   → 期次合计 {eid_n} / {total} = {eid_n/total*100:.1f}%\n")

print(f"总 {GN} / {GT} = {GN/GT*100:.1f}%")
Path(ROOT / "tools/_b18_dtable.txt").write_text(
    "\n".join(f"{e}|{l}|{r}|{c}" for e, l, r, c in lines), encoding="utf-8"
)
