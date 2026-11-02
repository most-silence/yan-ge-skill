import re
from pathlib import Path
d = Path(r"sources\05-播客转写\audio_txt")
f = {"xXbq00mp4j8C":"xXbq00mp4j8C_眼哥股市会 5月18日._clean.txt",
 "A8RQb9NRe5Zs":"A8RQb9NRe5Zs_眼哥股市会 8月12日._clean.txt",
 "9BJToFj5QFAr":"9BJToFj5QFAr_眼哥股市会 9月10日._clean.txt",
 "pEzd4aIgCMlt":"pEzd4aIgCMlt_说在8月开盘前._clean.txt"}
def i(t): h,m,s=map(int,t.split(":")); return h*3600+m*60+s
SEG = {
 "xXbq00mp4j8C": [("开场寒暄/生日祝福/节目定位/对谈预告","00:00:00","00:04:36"),
                  ("板块口播被打断","00:12:16","00:12:46"),
                  ("收尾","00:16:56","00:17:29")],
 "A8RQb9NRe5Zs": [("片头","00:00:00","00:00:33"),
                  ("红色火箭推广","00:03:35","00:07:39"),
                  ("个股即时闲聊","00:17:35","00:19:56")],
 "9BJToFj5QFAr": [("教师节致辞","00:00:00","00:01:00"),
                  ("答听众与外盘叙述","00:08:19","00:16:00"),
                  ("零碎","00:02:00","00:02:10")],
 "pEzd4aIgCMlt": [("周末生活/旅行/人生幻想","00:00:00","00:07:45"),
                  ("情绪抒发/留与走","00:08:28","00:11:52")],
}
T=N=0
for eid,path in f.items():
    rows=[(i(m.group(1)), m.group(2)) for m in (re.match(r"^\[(\d{2}:\d{2}:\d{2})\] (.*)$", l) for l in (d/path).read_text(encoding="utf-8").splitlines()) if m]
    t=sum(len(x[1]) for x in rows); T+=t
    print(f"## {eid}  正文 {t} 字")
    sub=0
    for name,a,b in SEG[eid]:
        n=sum(len(tx) for ts,tx in rows if i(a)<=ts<i(b))
        sub+=n
        print(f"   {name:28s} {a}~{b}  {n:5d} 字")
    print(f"   小计 {sub} 字 = {sub/t*100:.1f}%")
    N+=sub
print(f"\n合计 {T} 字，噪音 {N} 字 = {N/T*100:.1f}%")
