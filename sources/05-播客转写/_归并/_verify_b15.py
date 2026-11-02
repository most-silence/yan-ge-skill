# -*- coding: utf-8 -*-
"""B15 归并产物自检：引文逐字、期次/时间戳真实、对账完整、规则编号连续。"""
import io, re

BUC = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_分桶\B15-做T.md'
OUT = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\B15-做T.md'

buc = io.open(BUC, encoding='utf-8').read()
out = io.open(OUT, encoding='utf-8').read()

fail = 0

# ---------- 1) 桶内候选清单 ----------
cand_ids = re.findall(r'^## (B15-\d{3}) · ', buc, re.M)
print('bucket candidates:', len(cand_ids), 'unique:', len(set(cand_ids)))
assert cand_ids == ['B15-%03d' % i for i in range(1, 62)], 'bucket candidate list not 001..061'

# ---------- 2) 对账表：61 行、连续、无重复 ----------
rows = re.findall(r'^\| (B15-\d{3}) \| → (.+?) \|$', out, re.M)
print('recon rows:', len(rows))
ids = [r[0] for r in rows]
if ids != ['B15-%03d' % i for i in range(1, 62)]:
    fail += 1
    print('FAIL recon rows not 001..061 in order; missing:', set(cand_ids) - set(ids), 'extra:', set(ids) - set(cand_ids))

# ---------- 3) 规则节点编号连续 ----------
nodes = re.findall(r'^#{3,4} ((?:M|S)\d{2}(?:-[A-Z])?) · ', out, re.M)
main = [n for n in nodes if '-' not in n]
print('main rules:', main)
if main != ['M%02d' % i for i in range(1, len(main) + 1)]:
    fail += 1
    print('FAIL main rule numbering not continuous from M01')

# ---------- 4) 引文逐字：每条引文行必须是桶文件子串 ----------
quote_lines = [l for l in out.split('\n') if l.startswith('> [0') or l.startswith('> 「')]
print('quote lines:', len(quote_lines))
bad_q = 0
for l in quote_lines:
    body = l[2:]
    if body not in buc:
        bad_q += 1
        print('QUOTE NOT VERBATIM:', repr(body[:90]))
fail += bad_q

# ---------- 5) 归因行：eid 与时间戳都必须真实存在于桶内 ----------
buc_eids = set(re.findall(r'`([A-Za-z0-9]{8,})`', buc))
buc_ts = set(re.findall(r'\[(\d{2}:\d{2}:\d{2})\]', buc))
attr = re.findall(r'^—— `([A-Za-z0-9]+)` `\[(\d{2}:\d{2}:\d{2})\]`(?:~`\[(\d{2}:\d{2}:\d{2})\]`)?', out, re.M)
print('attribution lines:', len(attr))
bad_a = 0
for eid, t1, t2 in attr:
    if eid not in buc_eids:
        bad_a += 1; print('BAD EID', eid)
    for t in (t1, t2):
        if t and t not in buc_ts:
            bad_a += 1; print('BAD TS', eid, t)
fail += bad_a

# ---------- 6) 待补声明与归入了覆盖 ----------
daibu = re.findall(r'\*\*待补\*\*', out)
print('待补 marks:', len(daibu))
daibu_nodes = re.findall(r'^#{3,4} ((?:M|S)\d{2}(?:-[A-Z])?) · .*$', out, re.M)
lines = out.split('\n')
nodes_with_daibu = set()
cur = None
for l in lines:
    m = re.match(r'^#{3,4} ((?:M|S)\d{2}(?:-[A-Z])?) · ', l)
    if m:
        cur = m.group(1)
    if '**待补**' in l and cur:
        nodes_with_daibu.add(cur)
print('nodes 待补:', sorted(nodes_with_daibu))

# 归入了 覆盖：并集应等于全部 61 条（父子同条允许重复出现）
groups = re.findall(r'- \*\*归入了\*\*：(.+)', out)
covered = set()
for g in groups:
    covered |= set(re.findall(r'B15-\d{3}', g))
print('归入了 union:', len(covered))
if covered != set(cand_ids):
    fail += 1
    print('FAIL 归入了 missing:', sorted(set(cand_ids) - covered), 'extra:', sorted(covered - set(cand_ids)))

# 每个规则节点都必须有「代表原话」字段
node_blocks = re.split(r'^#{3,4} ', out, flags=re.M)[1:]
no_quote = [b.split(' · ')[0] for b in node_blocks if '- **代表原话**' not in b]
print('nodes without 代表原话 field:', no_quote)
if no_quote:
    fail += 1

print('====== FAILURES:', fail)