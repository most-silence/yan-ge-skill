import re, pathlib
root = pathlib.Path(".")
batch = (root/"sources/05-播客转写/_batches/batch-34.md").read_text(encoding="utf-8")
# split into episodes by "## N." headings and eid
parts = re.split(r"\n## \d+\. ", batch)
eids = ["3Bo6JpZ2mKkQ","uoZOErokuN5G","SEGWta2l9CNo","qaMrCXIb2PFA"]
blocks = []
for p in parts[1:]:
    body = p.split("```")
    if len(body)>=3:
        blocks.append(body[1])
def lines(text):
    out={}
    for m in re.finditer(r"^\[(\d{2}:\d{2}:\d{2})\] (.*)$", text, re.M):
        out.setdefault(m.group(1), []).append(m.group(2))
    return out
for eid, b in zip(eids, blocks):
    cl = next(root.glob(f"sources/05-播客转写/audio_txt/{eid}_*._clean.txt")).read_text(encoding="utf-8")
    L1=lines(b); L2=lines(cl)
    diffs=0
    for ts,v in L1.items():
        if ts not in L2:
            print(eid,"missing in clean:",ts,v[:40]); diffs+=1
        elif v[0]!=L2[ts][0]:
            print(eid,"diff",ts); print("  batch:",v[0][:100]); print("  clean:",L2[ts][0][:100]); diffs+=1
    extra=[t for t in L2 if t not in L1]
    print(eid,"batch lines",len(L1),"clean lines",len(L2),"diffs",diffs,"extra in clean",extra[:10])
