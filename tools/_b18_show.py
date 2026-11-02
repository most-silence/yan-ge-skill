import re
from pathlib import Path
p = Path(r"sources\05-播客转写\_规则候选\batch-18.md")
t = p.read_text(encoding="utf-8")
secs = re.split(r"\n(?=### )", t)
for s in secs:
    if not re.match(r"### [ABC]\d+ · ", s):
        continue
    title = s.splitlines()[0]
    blk = re.search(r"((?:^> \[\d{2}:\d{2}:\d{2}\].*\n)+)", s, re.M)
    lines = [l for l in blk.group(1).splitlines()]
    print(title)
    print("   " + lines[0][:100])
    print("   " + lines[-1][:100])
    print()
