import importlib.util, sys
spec = importlib.util.spec_from_file_location("b37", r"tools\_b37_blocks.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
bad=[]
for k in m.SPECS:
    try:
        blk = m.build(k)
        n = blk.count(chr(10)+"> ")
        print(k, "OK", n+1, "lines")
    except SystemExit as e:
        bad.append((k,str(e)))
for k,e in bad: print("FAIL",k,e)
