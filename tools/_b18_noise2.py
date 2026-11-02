import re
from pathlib import Path
d = Path(r"sources\05-播客转写\audio_txt")
f = {"xXbq00mp4j8C":"xXbq00mp4j8C_眼哥股市会 5月18日._clean.txt",
 "A8RQb9NRe5Zs":"A8RQb9NRe5Zs_眼哥股市会 8月12日._clean.txt",
 "9BJToFj5QFAr":"9BJToFj5QFAr_眼哥股市会 9月10日._clean.txt",
 "pEzd4aIgCMlt":"pEzd4aIgCMlt_说在8月开盘前._clean.txt"}
def i(t): h,m,s=map(int,t.split(":")); return h*3600+m*60+s
# 精读后划定的噪音区间（含非规则闲聊/推广/情绪/答听众）
SEG = {
 "xXbq00mp4j8C": [("00:00:00","00:04:36"),("00:12:16","00:12:46"),("00:16:56","00:17:29")],
 "A8RQb9NRe5Zs": [("00:00:00","00:00:33"),("00:03:35","00:07:39"),("00:17:35","00:19:56")],
 "9BJToFj5QFAr": [("00:00:00","00:01:00"),("00:08:19","00:16:00"),("00:02:00","00:02:10")],
 "pEzd4aIgCMlt": [("00:00:00","00:07:45"),("00:08:28","00:11:52")],
}
T=N=0
for eid,path in f.items():
    rows=[]
    for l in (d/path).read_text(encoding="utf-8").splitlines():
        m=re.match(r"^\[(\d{2}:\d{2}:\d{2})\] (.*)$", l)
        if m: rows.append((i(m.group(1)), m.group(2)))
    t=sum(len(x[1]) for x in rows)
    wins=[(i(a),i(b)) for a,b in SEG[eid]]
    n=sum(len(tx) for ts,tx in rows if any(a<=ts<b for a,b in wins))
    print(f"{eid}  正文{t:6d}字  噪音{n:6d}字  {n/t*100:5.1f}%")
    T+=t; N+=n
print(f"合计 {T} 字 / 噪音 {N} 字 = {N/T*100:.1f}%")
