import importlib.util
spec = importlib.util.spec_from_file_location("b37", r"tools\_b37_blocks.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out=open(r"tools\_b37_dbg5.txt","w",encoding="utf-8")
def rng(eid, a, b):
    out.write(f"=== {eid} {a}~{b}\n")
    on=False
    for t,ln in m.load_lines(eid):
        if t==a: on=True
        if on: out.write(ln+"\n")
        if t==b and on: break
rng("UOVzuGdzs1dA","00:21:50","00:22:20")
rng("UOVzuGdzs1dA","00:24:25","00:24:45")
rng("UOVzuGdzs1dA","00:33:50","00:36:30")
rng("FW8NPflTV7gt","00:16:10","00:16:30")
out.write("\n== doubled ts lines ==\n")
for eid in ["pp9CcfoGIEKl","UOVzuGdzs1dA","FW8NPflTV7gt","ZCI83GD81iH7"]:
    n=0
    for t,ln in m.load_lines(eid):
        if ln.count("[00:")>1: n+=1
    out.write(f"{eid}: {n}\n")
out.close()
