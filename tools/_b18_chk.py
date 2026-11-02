import re
from pathlib import Path
p = Path(r"sources\05-播客转写\_规则候选\batch-18.md")
t = p.read_text(encoding="utf-8")
# split into sections by ### 
secs = re.split(r"\n(?=### )", t)
for s in secs:
    if not s.startswith("### "):
        continue
    title = s.splitlines()[0][:40]
    hdr = re.search(r"\| 时间戳 \| `\[(.+?)\]`~`\[(.+?)\]` \|", s)
    foot = re.search(r"—— `([A-Za-z0-9]+)` `\[(.+?)\]`~`\[(.+?)\]`", s)
    if not hdr or not foot:
        print("NO-HEADER/FOOT:", title, "| hdr", bool(hdr), "foot", bool(foot))
        continue
    if (hdr.group(1), hdr.group(2)) != (foot.group(2), foot.group(3)):
        print("MISMATCH:", title)
        print("   hdr :", hdr.group(1), hdr.group(2))
        print("   foot:", foot.group(2), foot.group(3))
