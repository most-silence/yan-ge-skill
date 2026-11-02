import importlib.util
spec = importlib.util.spec_from_file_location("b37", r"tools\_b37_blocks.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out=open(r"tools\_b37_dbg3.txt","w",encoding="utf-8")
for eid in ["FW8NPflTV7gt","UOVzuGdzs1dA","pp9CcfoGIEKl","ZCI83GD81iH7"]:
    hits = list(m.TXT_DIR.glob(f"{eid}_*"))
    for h in hits:
        t = h.read_text(encoding="utf-8", errors="ignore")
        ls = t.splitlines()
        ts = [l for l in ls if l.strip().startswith("[")]
        out.write(f"{h.name}\t lines={len(ls)}\t ts_lines={len(ts)}\t chars={len(t)}\n")
        out.write(f"   first_ts={ts[0][:20] if ts else None}\n   last_ts={ts[-1][:60] if ts else None}\n")
out.close()
