import re
from pathlib import Path
d = Path(r"sources\05-播客转写\audio_txt")
f = {"xXbq00mp4j8C":"xXbq00mp4j8C_眼哥股市会 5月18日._clean.txt",
 "A8RQb9NRe5Zs":"A8RQb9NRe5Zs_眼哥股市会 8月12日._clean.txt",
 "9BJToFj5QFAr":"9BJToFj5QFAr_眼哥股市会 9月10日._clean.txt",
 "pEzd4aIgCMlt":"pEzd4aIgCMlt_说在8月开盘前._clean.txt"}
md = Path(r"sources\05-播客转写\_规则候选\batch-18.md").read_text(encoding="utf-8")
secs = re.split(r"\n(?=### )", md)
cited = {}
for s in secs:
    m = re.search(r"—— `([A-Za-z0-9]+)` `\[(\d{2}:\d{2}:\d{2})\]`~`\[(\d{2}:\d{2}:\d{2})\]`", s)
    if m: cited.setdefault(m.group(1), []).append((m.group(2), m.group(3)))

def s2i(t): h,mm,ss = map(int,t.split(":")); return h*3600+mm*60+ss
tot_sec = {}
for eid,path in f.items():
    rows=[]
    for l in (d/path).read_text(encoding="utf-8").splitlines():
        m=re.match(r"^\[(\d{2}:\d{2}:\d{2})\] (.*)$", l)
        if m: rows.append((m.group(1), m.group(2)))
    # 每行覆盖到下一行时间戳，算"秒"
    spans=[]
    for i,(ts,tx) in enumerate(rows):
        end = s2i(rows[i+1][0]) if i+1<len(rows) else s2i(ts)+3
        spans.append((s2i(ts), end, len(tx)))
    total_s = spans[-1][1]-spans[0][0]
    total_c = sum(x[2] for x in spans)
    # 引文覆盖
    cov_s=0; cov_c=0
    wins = [(s2i(a), s2i(b)) for a,b in cited.get(eid,[])]
    for a,b,c in spans:
        hit = any(not (b<=wa or a>=wb+1) for wa,wb in wins)
        if hit: cov_s += b-a; cov_c += c
    print(f"{eid}  时长{total_s//60:>3}分  正文{total_c:6d}字  引文覆盖 {cov_s/60:5.1f}分 {cov_c/total_c*100:5.1f}%  未覆盖{(total_s-cov_s)/60:5.1f}分")
