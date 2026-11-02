# -*- coding: utf-8 -*-
import io, re, importlib.util, os

OUT = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\B21-资金_主力.md'
spec = importlib.util.spec_from_file_location('b', r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\_gen_base.py')
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
out = io.open(OUT, encoding='utf-8').read()

# 1) attribution lines must literally match a bucket attribution
buc = io.open(base.BUCKET, encoding='utf-8').read()
btrip = set()
for m in re.finditer(r'`([A-Za-z0-9]{8,})`\s*`\[([0-9:]+)\]`', buc):
    btrip.add((m.group(1), m.group(2)))

bad = 0
for m in re.finditer(r'- \*\*代表原话\*\*（`B21-(\d{3})`）：.*?\n—— `([A-Za-z0-9]+)` `\[([0-9:]+)\]`', out, re.S):
    eid, ts = m.group(2), m.group(3)
    if (eid, ts) not in btrip:
        bad += 1
        print('ATTR NOT IN BUCKET', m.group(1), eid, ts)
print('attribution not-in-bucket:', bad)

# 2) "归因" notes must cite an evidence header that exists in the bucket block
bad2 = 0
for m in re.finditer(r'- \*\*代表原话\*\*（`B21-(\d{3})`）：.*?—— 归因：[^\n]*?：`([A-Za-z0-9]+)` `\[([0-9:]+)\]`', out, re.S):
    cnum, eid, ts = m.group(1), m.group(2), m.group(3)
    ev = base.cand[cnum]['ev']
    if not any(e == eid and t == ts for e, t, _ in ev):
        bad2 += 1
        print('EVIDENCE HEAD NOT FOUND', cnum, eid, ts, ev)
print('evidence-head mismatches:', bad2)

# 3) counting sanity
print('待补 lines:', len(re.findall(r'- \*\*代表原话\*\*：⚠️ \*\*待补\*\*', out)))
print('引文缺口 lines:', len(re.findall(r'^- \*\*引文缺口\*\*：', out, re.M)))
print('未标归因 quote notes:', out.count('桶内该条原话未标归因'))
print('被截断 quote notes:', out.count('桶内该条引文本身在归因处被截断'))
print('rendered quotes:', len(re.findall(r'- \*\*代表原话\*\*（', out)))
print('rules:', len(re.findall(r'^#{3,4} [MS]\d+', out, re.M)))
