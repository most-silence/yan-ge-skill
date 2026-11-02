import re
from pathlib import Path
d = Path(r"sources\05-播客转写\audio_txt")
f = {"xXbq00mp4j8C":"xXbq00mp4j8C_眼哥股市会 5月18日._clean.txt",
 "A8RQb9NRe5Zs":"A8RQb9NRe5Zs_眼哥股市会 8月12日._clean.txt",
 "9BJToFj5QFAr":"9BJToFj5QFAr_眼哥股市会 9月10日._clean.txt",
 "pEzd4aIgCMlt":"pEzd4aIgCMlt_说在8月开盘前._clean.txt"}
def show(eid,a,b):
    print("---",eid,a,b)
    for l in (d/f[eid]).read_text(encoding="utf-8").splitlines():
        m=re.match(r"^\[(\d{2}:\d{2}:\d{2})\] ",l)
        if m and a<=m.group(1)<=b: print(l)
show("9BJToFj5QFAr","00:12:50","00:13:16")
show("pEzd4aIgCMlt","00:08:04","00:08:22")
show("xXbq00mp4j8C","00:15:10","00:15:25")
