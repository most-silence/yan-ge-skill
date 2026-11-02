# -*- coding: utf-8 -*-
"""交叉校验：对账表落点 vs 各规则「归入了」；总表期次计数 vs 实际期次去重。"""
import io, re

BUC = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_分桶\B15-做T.md'
OUT = r'E:\AIProjetct\Nothing\眼哥\sources\05-播客转写\_归并\B15-做T.md'
buc = io.open(BUC, encoding='utf-8').read()
out = io.open(OUT, encoding='utf-8').read()

# 桶内：候选 -> 期次
blocks = re.split(r'^## (B15-\d{3}) · ', buc, flags=re.M)[1:]
cand_eid = {}
for i in range(0, len(blocks), 2):
    cid = blocks[i]
    body = blocks[i + 1]
    m = re.search(r'\| 期次 \| `([A-Za-z0-9]+)`', body)
    cand_eid[cid] = m.group(1)

# 归并产物：节点 -> 归入了
nodes = {}
cur = None
for l in out.split('\n'):
    m = re.match(r'^#{3,4} ((?:M|S)\d{2}(?:-[A-Z])?) · ', l)
    if m:
        cur = m.group(1); nodes[cur] = []
    m2 = re.match(r'- \*\*归入了\*\*：(.+)', l)
    if m2 and cur:
        nodes[cur] = re.findall(r'B15-\d{3}', m2.group(1))
# 父子关系
parent_of = {'M01-A': 'M01', 'M06-A': 'M06', 'M09-A': 'M09', 'M13-A': 'M13'}
child_of = {v: k for k, v in parent_of.items()}

routes = dict(re.findall(r'^\| (B15-\d{3}) \| → (M\d{2}(?:-[A-Z])?)', out, re.M))
print('routes:', len(routes))

bad = 0
for cid, r in routes.items():
    ok = cid in nodes.get(r, [])
    if not ok and r in child_of:            # 落在子节点、但写在父的归入了
        ok = cid in nodes.get(child_of[r], [])
    if not ok and r in parent_of:           # 落在父节点、但写在子的归入了（B15-045）
        ok = cid in nodes.get(parent_of[r], [])
    if not ok:
        bad += 1
        print('ROUTE NOT BACKED', cid, r, nodes.get(r))
print('route mismatches:', bad)

# 总表期次计数 vs 实际去重期次
tbl = dict((m[0], int(m[1])) for m in re.findall(r'^\| (M\d{2}(?:-[A-Z])?) \| [^|]+ \| (\d+) \|', out, re.M))
for node, cnt in sorted(tbl.items()):
    ids = set(cand_eid[c] for c in nodes.get(node, []))
    flag = '' if len(ids) == cnt else '  <== MISMATCH'
    if flag:
        bad += 1
    print('%-6s table=%d actual=%d%s' % (node, cnt, len(ids), flag))
print('====== FAILURES:', bad)