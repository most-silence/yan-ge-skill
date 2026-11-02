import importlib.util
spec = importlib.util.spec_from_file_location("b37", r"tools\_b37_blocks.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out=open(r"tools\_b37_check2.txt","w",encoding="utf-8")
bad=[]
for k in m.SPECS:
    try:
        blk=m.build(k)
        out.write(f"{k} OK lines={blk.count(chr(10)+'> ')+1}\n")
    except SystemExit as e:
        bad.append((k,str(e)))
for k,e in bad: out.write(f"FAIL {k} {e}\n")
out.write(f"\nbad={len(bad)}\n")
# 顺带打印 E2 关键词位置确认
for kw in ["闲钱","葡萄","项目统","巴菲特"]:
    hit=[t for t,ln in m.load_lines("UOVzuGdzs1dA") if kw in ln]
    out.write(f"E2 {kw}: {hit}\n")
out.close()
