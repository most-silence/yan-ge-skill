import re
from pathlib import Path
d = Path(r"sources\05-播客转写\audio_txt")
files = {
 "xXbq00mp4j8C":"xXbq00mp4j8C_眼哥股市会 5月18日._clean.txt",
 "A8RQb9NRe5Zs":"A8RQb9NRe5Zs_眼哥股市会 8月12日._clean.txt",
 "9BJToFj5QFAr":"9BJToFj5QFAr_眼哥股市会 9月10日._clean.txt",
 "pEzd4aIgCMlt":"pEzd4aIgCMlt_说在8月开盘前._clean.txt",
}
for eid,f in files.items():
    t = (d/f).read_text(encoding="utf-8")
    body = "\n".join(l for l in t.splitlines() if re.match(r"^\[\d{2}:\d{2}:\d{2}\] ", l))
    n = len(re.sub(r"^\[\d{2}:\d{2}:\d{2}\] ", "", body, flags=re.M).replace("\n",""))
    print(eid, "chars:", n)
print()
# 抽查几个窗口的行
def show(f, a, b):
    t=(d/f).read_text(encoding="utf-8").splitlines()
    print("---", a, b)
    for l in t:
        m=re.match(r"^\[(\d{2}:\d{2}:\d{2})\] ", l)
        if m and a<=m.group(1)<=b: print(l)
show(files["xXbq00mp4j8C"], "00:14:16","00:14:20")
show(files["9BJToFj5QFAr"], "00:16:43","00:16:52")
show(files["A8RQb9NRe5Zs"], "00:17:36","00:18:10")
show(files["pEzd4aIgCMlt"], "00:05:38","00:05:56")
