import importlib.util
spec = importlib.util.spec_from_file_location("b37", r"tools\_b37_blocks.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out=open(r"tools\_b37_view.txt","w",encoding="utf-8")
for k in m.SPECS:
    out.write("\n########## "+k+"\n")
    out.write(m.build(k)+"\n")
out.close()
