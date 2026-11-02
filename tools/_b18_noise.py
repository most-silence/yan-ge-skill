import re
from pathlib import Path
d = Path(r"sources\05-播客转写\audio_txt")
f = {"xXbq00mp4j8C":"xXbq00mp4j8C_眼哥股市会 5月18日._clean.txt",
 "A8RQb9NRe5Zs":"A8RQb9NRe5Zs_眼哥股市会 8月12日._clean.txt",
 "9BJToFj5QFAr":"9BJToFj5QFAr_眼哥股市会 9月10日._clean.txt",
 "pEzd4aIgCMlt":"pEzd4aIgCMlt_说在8月开盘前._clean.txt"}
# 噪音区间（按时间戳粗切，只算正文里的字符）
SEG = {
 "xXbq00mp4j8C": [("00:00:00","00:04:36"),("00:12:22","00:12:46")],
 "A8RQb9NRe5Zs": [("00:03:35","00:07:39"),("00:17:35","00:19:30"),("00:00:00","00:00:30")],
 "9BJToFj5QFAr": [("00:00:00","00:01:00"),("00:08:19","00:19:20"),("00:02:00","00:02:10")],
 "pEzd4aIgCMlt": [("00:00:00","00:07:45"),("00:08:28","00:11:24")],
}
tot=0; noi=0
for eid,path in f.items():
    rows=[]
    for l in (d/path).read_text(encoding="utf-8").splitlines():
        m=re.match(r"^\[(\d{2}:\d{2}:\d{2})\] (.*)$", l)
        if m: rows.append((m.group(1), m.group(2)))
    t_chars=sum(len(r[1]) for r in rows)
    n_chars=0
    for a,b in SEG[eid]:
        n_chars += sum(len(r[1]) for r in rows if a<=r[0]<b)
    print(f"{eid}  total={t_chars:6d}  noise={n_chars:6d}  {n_chars/t_chars*100:5.1f}%")
    tot+=t_chars; noi+=n_chars
print(f"合计 total={tot} noise={noi}  {noi/tot*100:.1f}%")
