import importlib.util
spec = importlib.util.spec_from_file_location("b37", r"tools\_b37_blocks.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out=open(r"tools\_b37_dbg6.txt","w",encoding="utf-8")
lines=m.load_lines("FW8NPflTV7gt")
out.write("total %d\n"%len(lines))
for kw in ["闲钱","葡萄","项目统","十种","巴菲特"]:
    hit=[(i,t,ln) for i,(t,ln) in enumerate(lines) if kw in ln]
    out.write(f"{kw}: {len(hit)}\n")
    for i,t,ln in hit[:5]: out.write(f"   idx={i} ts={t} {ln[:80]}\n")
out.write("\nlast 20 lines:\n")
for i,(t,ln) in enumerate(lines[-20:]):
    out.write(f"   {t} {ln[:70]}\n")
out.close()
