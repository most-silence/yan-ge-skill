# -*- coding: utf-8 -*-
import io, re

OUT = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\B21-资金_主力.md'
BUC = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_分桶\B21-资金_主力.md'
out = io.open(OUT, encoding='utf-8').read()
buc = io.open(BUC, encoding='utf-8').read()

# --- bucket: block id -> (raw quote line, has_attribution) ---
bq = {}
cur = None
for ln in buc.split('\n'):
    m = re.match(r'^## B21-(\d{3}) · ', ln)
    if m:
        cur = m.group(1); continue
    if cur and ln.startswith('- **原话**：'):
        raw = ln[len('- **原话**：'):]
        has_attr = '—— `' in raw
        body = raw[:raw.find('—— `')].rstrip() if has_attr else raw.rstrip()
        bq[cur] = (body, has_attr)

def norm(s):
    s = s.replace('\n> ', '\n')
    while s.startswith('> '):
        s = s[2:]
    s = re.sub(r'\s*⚠️（桶内该条原话在 .*? 处被截断，照录，未补字）$', '', s)
    s = re.sub(r'\s*⚠️（桶内该条未标归因.*?）$', '', s)
    return s.rstrip()

# --- output: per rule node, which candidate's quote was used ---
# re-derive from generator map instead of parsing
import importlib.util, os
HERE = os.path.dirname(BUC)
spec = importlib.util.spec_from_file_location('b', r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\_gen_base.py')
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)

pat = re.compile(r'###+ (M\d+(?:-A)?|S\d+) · .*?\n\n- \*\*代表原话\*\*：\n\n(.*?)\n\n—— `([A-Za-z0-9]+)` `\[([0-9:]*)\]`', re.S)
found = pat.findall(out)
print('quote blocks found', len(found))
bad = 0
for node, body, eid, ts in found:
    if body.startswith('- '):   # 待补 form, skip
        continue
    used = [c for c in base.M[node] if base.cand[c]['quote'] is not None]
    b = min(used, key=lambda c: used.index(c))
    # generator uses R_['quote']; find the candidate whose bucket body matches
    match = None
    for c in used:
        if norm(body) == norm(bq[c][0]):
            match = c; break
    if match is None:
        bad += 1
        print('NO BUCKET MATCH', node, eid, repr(norm(body)[:90]))
        continue
    body_ok = norm(body) == norm(bq[match][0])
    eid_ok = (eid in base.cand[match]['eps'])
    ts_in_body = ('[%s]' % ts) in body
    if not (body_ok and eid_ok and ts_in_body):
        bad += 1
        print('ISSUE', node, match, 'body', body_ok, 'eid', eid_ok, 'ts', ts_in_body)
print('bad', bad)

# attribution coverage
noattr = [c for c, (b, h) in bq.items() if not h]
print('bucket quotes without attribution:', len(noattr), noattr)
