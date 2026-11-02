import re
from pathlib import Path

t = Path(r"sources\05-播客转写\_规则候选\batch-18.md").read_text(encoding="utf-8")


def i(x):
    h, m, s = map(int, x.split(":"))
    return h * 3600 + m * 60 + s


QW = re.compile(r"—— `([A-Za-z0-9]+)` `\[(\d\d:\d\d:\d\d)\]`~`\[(\d\d:\d\d:\d\d)\]`")
qw = [(m.group(1), i(m.group(2)), i(m.group(3))) for m in QW.finditer(t)]

dsec = t.split("## D. rejected")[1].split("## E.")[0]

# §D 每行都带期次 + 区间，按行配对
rows = re.findall(r"(?m)^\| `([A-Za-z0-9]+)` \|.*（(\d\d:\d\d:\d\d)[–-](\d\d:\d\d:\d\d)）", dsec)
dw = [(e, i(a), i(b)) for e, a, b in rows]
print("引文窗口", len(qw), "｜ D 区间", len(dw))

bad = []
for qe, qa, qb in qw:
    for de, da, db in dw:
        if qe == de and not (qb <= da or qa >= db):
            bad.append((qe, qa, qb, da, db))
print("同期内与噪音段重叠:", bad if bad else "无")

# 引文覆盖率
tot = {}
for e, a, b in qw:
    tot[e] = tot.get(e, 0) + (b - a)
for e in sorted(tot):
    print(f"  {e} 引文覆盖 {tot[e]} 秒 = {tot[e]/60:.1f} 分")
