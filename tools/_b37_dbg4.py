import importlib.util
spec = importlib.util.spec_from_file_location("b37", r"tools\_b37_blocks.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out=open(r"tools\_b37_dbg4.txt","w",encoding="utf-8")
lines = m.load_lines("FW8NPflTV7gt")
start=None
for i,(t,ln) in enumerate(lines):
    if t=="00:33:50": start=i
    if t=="00:36:30": end=i
for t,ln in lines[start:end+1]:
    out.write(ln+"\n")
out.write("\n==== batch excerpts ====\n")
b=open(r"sources\05-播客转写\_batches\batch-37.md",encoding="utf-8").read()
for kw in ["闲钱","葡萄","项目统","十种","再卖多少"]:
    out.write(f"--{kw}: {b.count(kw)}\n")
out.close()
