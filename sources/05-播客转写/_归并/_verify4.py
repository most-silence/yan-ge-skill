# -*- coding: utf-8 -*-
import io, re, os, importlib.util

OUT = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\B21-资金_主力.md'
BUC = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_分桶\B21-资金_主力.md'
spec = importlib.util.spec_from_file_location('b', r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\_gen_base.py')
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)

out = io.open(OUT, encoding='utf-8').read()

def strip_bucket(raw):
    """body = bucket quote text with blockquote markers removed and attribution removed"""
    raw = raw.rstrip()
    m = re.search(r'——\s*`[A-Za-z0-9]+`\s*`\[[0-9:]+\]`\s*$', raw)
    if m:
        raw = raw[:m.start()].rstrip()
    else:
        cut = raw.find('—— `')
        if cut >= 0:
            raw = raw[:cut].rstrip()
    lines = []
    for ln in raw.split('\n'):
        s = ln
        while s.startswith('> '):
            s = s[2:]
        while s.startswith('>'):
            s = s[1:]
        lines.append(s.rstrip())
    return '\n'.join(lines).strip('\n')

# --- verify every rendered quote body equals its bucket body ---
blocks = re.findall(r'- \*\*代表原话\*\*（`B21-(\d{3})`）：\n\n((?:>.*\n)+)\n—— ', out)
print('rendered quote blocks', len(blocks))
bad = 0
for cnum, body in blocks:
    got = '\n'.join(l[2:] if l.startswith('> ') else ('' if l == '>' else l)
                    for l in body.rstrip('\n').split('\n'))
    want = strip_bucket(base.cand[cnum]['quote'])
    if got != want:
        bad += 1
        print('MISMATCH B21-%s' % cnum)
        print('  got :', repr(got[:160]))
        print('  want:', repr(want[:160]))
print('quote mismatch count:', bad)

# --- verify attribution line's eid/ts really belong to that candidate ---
bad2 = 0
for m in re.finditer(r'- \*\*代表原话\*\*（`B21-(\d{3})`）：\n\n((?:>.*\n)+)\n—— `([A-Za-z0-9]+)` `\[([0-9:]+)\]`', out):
    cnum, body, eid, ts = m.group(1), m.group(2), m.group(3), m.group(4)
    d = base.cand[cnum]
    ok_eid = eid in d['eps']
    ok_ts = ('[%s]' % ts) in body
    if not (ok_eid and ok_ts):
        bad2 += 1
        print('ATTR ISSUE B21-%s eid=%s(%s) ts=%s(%s)' % (cnum, eid, ok_eid, ts, ok_ts))
print('attribution issues:', bad2)

# --- structural checks ---
L = out.split('\n')
h2 = [l for l in L if l.startswith('## ')]
h3 = [l for l in L if l.startswith('### ')]
h4 = [l for l in L if l.startswith('#### ')]
print('H2', h2)
print('H3', len(h3), 'H4', len(h4), [x.split(' · ')[0] for x in h4])

nums = re.findall(r'B21-(\d{3}) \| → ', out)
exp = ['%03d' % i for i in range(1, 359)]
print('recon rows', len(nums), 'unique', len(set(nums)), 'continuous', nums == exp)

nodes = re.findall(r'^#{3,4} (M\d+-A|M\d+|S\d+) · ', out, re.M)
print('nodes', len(nodes), 'unique', len(set(nodes)))
missing_nodes = [k for k in base.ORDER if k not in nodes]
print('missing nodes', missing_nodes)

# 归入了 must list exactly the mapped candidates
bad3 = 0
for k in base.ORDER:
    m = re.search(r'^#{3,4} %s · .*?\n(.*?)(?=^#{3,4} |\Z)' % re.escape(k), out, re.S | re.M)
    seg = m.group(1)
    got = re.findall(r'B21-(\d{3})', re.search(r'- \*\*归入了\*\*：(.+)', seg).group(1))
    if got != base.M[k]:
        bad3 += 1
        print('归入了 MISMATCH', k, got, base.M[k])
print('归入了 mismatches', bad3)

print('待补', out.count('**待补**'), '引文缺口', out.count('**引文缺口**'),
      '未标归因', out.count('未标归因'), '被截断', out.count('被截断'))
print('bytes', len(out.encode('utf-8')), 'lines', len(L))
