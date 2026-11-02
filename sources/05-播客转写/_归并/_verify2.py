# -*- coding: utf-8 -*-
import io, re

OUT = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\B21-资金_主力.md'
BUC = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_分桶\B21-资金_主力.md'
out = io.open(OUT, encoding='utf-8').read()
buc = io.open(BUC, encoding='utf-8').read()

# collect (quote_body, eid, ts) triples from the bucket
btrip = set()
for ln in buc.split('\n'):
    if ln.startswith('- **原话**：'):
        body = ln[len('- **原话**：'):]
        i = body.find('—— `')
        if i >= 0:
            body = body[:i].rstrip()
        for m in re.finditer(r'`([A-Za-z0-9]{8,})`\s*`\[([0-9:]+)\]`', ln):
            btrip.add((body.rstrip(), m.group(1), m.group(2)))
print('bucket triples', len(btrip))

pat = re.compile(r'- \*\*代表原话\*\*：\n\n(.*?)\n\n—— `([A-Za-z0-9]+)` `\[([0-9:]*)\]`', re.S)
blocks = pat.findall(out)
ok = 0
for body, eid, ts in blocks:
    clean = body.replace('\n> ', '\n')
    if clean.startswith('> '):
        clean = clean[2:]
    clean = re.sub(r'\s*⚠️（桶内该条原话在 .*? 处被截断，照录，未补字）$', '', clean)
    # find the bucket triple whose body == clean and eid matches
    hits = [t for t in btrip if t[0] == clean and t[1] == eid]
    if hits:
        if ts not in [h[2] for h in hits]:
            print('TS MISMATCH', eid, ts, [h[2] for h in hits])
        else:
            ok += 1
    else:
        print('NO TRIPLE MATCH', eid, repr(clean[:100]))
print('verified triples', ok, '/', len(blocks))
