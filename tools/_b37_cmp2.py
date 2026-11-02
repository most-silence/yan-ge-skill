import re
b=open(r"sources\05-播客转写\_batches\batch-37.md",encoding="utf-8").read()
parts=re.split(r"\n## ", b)
out=open(r"tools\_b37_cmp2.txt","w",encoding="utf-8")
for i,sec in enumerate(parts):
    head=sec.splitlines()[0][:40]
    blocks=sec.split("```")
    nb=len(blocks)
    out.write(f"--- part{i} head={head} fenced={nb}\n")
    if nb>=3:
        body=blocks[1]
        bl=[l.strip() for l in body.splitlines() if l.strip().startswith("[")]
        out.write(f"    lines={len(bl)} first={bl[0][:30]} last={bl[-1][:30]}\n")
        out.write(f"    has xianqian={'闲钱' in body} has bafeite={'巴菲特' in body}\n")
out.close()
