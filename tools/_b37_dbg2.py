import importlib.util, io, sys
spec = importlib.util.spec_from_file_location("b37", r"tools\_b37_blocks.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out = open(r"tools\_b37_dbg2.txt","w",encoding="utf-8")
def grep(eid, frag):
    lines = m.load_lines(eid)
    out.write(f"=== {eid} :: {frag}\n")
    for t, ln in lines:
        if frag in ln:
            out.write(f"  [{t}] {ln}\n")
for eid, frag in [("pp9CcfoGIEKl","闲钱"),("FW8NPflTV7gt","闲钱去做投资"),("FW8NPflTV7gt","葡萄"),("FW8NPflTV7gt","项目统"),("FW8NPflTV7gt","再卖多少"),("FW8NPflTV7gt","包括今天"),("FW8NPflTV7gt","可以说十种")]:
    grep(eid,frag)
lines = m.load_lines("FW8NPflTV7gt")
out.write("\n=== FW8NPflTV7gt line count: %d\n" % len(lines))
for t, ln in lines[-60:]:
    out.write(f"  [{t}] {ln}\n")
out.close()
