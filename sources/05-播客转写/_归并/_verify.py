# -*- coding: utf-8 -*-
import io, re, sys

OUT = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\B21-资金_主力.md'
BUC = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_分桶\B21-资金_主力.md'

out = io.open(OUT, encoding='utf-8').read()
buc = io.open(BUC, encoding='utf-8').read()

pat = re.compile(r'- \*\*代表原话\*\*：\n\n(.*?)\n\n—— `([A-Za-z0-9]+)` `\[([0-9:]*)\]`', re.S)
blocks = pat.findall(out)
print('quote_blocks', len(blocks))

bad = 0
for body, eid, ts in blocks:
    clean = body.replace('\n> ', '\n')
    if clean.startswith('> '):
        clean = clean[2:]
    clean = re.sub(r'\s*⚠️（桶内该条原话在 .*? 处被截断，照录，未补字）$', '', clean)
    if clean not in buc:
        bad += 1
        print('MISMATCH', eid, repr(clean[:140]))
print('mismatch', bad)

# every quote block's eid must be a real episode id in bucket
eids = set(re.findall(r'`([A-Za-z0-9]{8,})`', buc))
for body, eid, ts in blocks:
    if eid not in eids:
        print('BAD EID', eid)

# every timestamp must be real
for body, eid, ts in blocks:
    m = re.search(r'\[(%s)\]' % re.escape(ts), body)
    if not m:
        print('TS NOT IN BODY', eid, ts)

print('待补', out.count('**待补**'))
print('引文缺口', out.count('**引文缺口**'))
