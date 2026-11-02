import sys, io, re, glob, os
def conv(srt, txt):
    with io.open(srt, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    blocks = re.split(r"\r?\n\r?\n", raw.strip())
    out = []
    for b in blocks:
        ls = [x for x in b.splitlines() if x.strip()]
        if len(ls) < 3:
            continue
        m = re.search(r"(\d{1,2}):(\d{2}):(\d{2})[,.]\d{1,3}\s*-->", ls[1] if not re.search(r"-->" , ls[0]) else ls[0])
        if not m:
            continue
        ts = f"[{int(m.group(1)):02d}:{m.group(2)}:{m.group(3)}]"
        start_idx = 2 if not re.search(r"-->", ls[0]) else 1
        text = " ".join(ls[start_idx:]).strip()
        if text:
            out.append(f"{ts} {text}")
    with io.open(txt, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    return len(out)
for srt in sorted(glob.glob(r"E:\AIProjetct\Nothing\眼哥\sources\02-抖音视频\*.srt")):
    txt = srt[:-4] + ".txt"
    n = conv(srt, txt)
    print(f"{os.path.basename(txt)[:52]:54s} {n:5d} lines  {os.path.getsize(txt):>9,} B")
