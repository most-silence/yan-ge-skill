import re
b=open(r"sources\05-播客转写\_batches\batch-37.md",encoding="utf-8").read()
# split episodes
parts=re.split(r"\n## \d+\. ", b)
out=open(r"tools\_b37_cmp.txt","w",encoding="utf-8")
eids={
 1:"pp9CcfoGIEKl",2:"UOVzuGdzs1dA",3:"FW8NPflTV7gt",4:"ZCI83GD81iH7"}
for i in range(1,5):
    sec=parts[i]
    body=sec.split("```")[1]
    bl=[l.strip() for l in body.splitlines() if l.strip().startswith("[")]
    eid=eids[i]
    cl=[l.strip() for l in open(f"sources/05-播客转写/audio_txt/{eid}_"+{"pp9CcfoGIEKl":"眼哥股市会 7.21日","UOVzuGdzs1dA":"眼哥股市会 9月23日","FW8NPflTV7gt":"眼哥股市会 1月26日","ZCI83GD81iH7":"眼哥股市会 3月26日"}[eid]+"._clean.txt",encoding="utf-8")]
    cl=[l for l in cl if l.startswith("[")]
    cs=set(cl)
    missing=[l for l in bl if l not in cs]
    out.write(f"=== ep{i} {eid}: batch={len(bl)} clean={len(cl)} missing={len(missing)}\n")
    for m in missing[:15]: out.write("   MISS "+m[:90]+"\n")
    if missing:
        out.write("   first missing idx=%d of %d\n" % (bl.index(missing[0]), len(bl)))
out.close()
