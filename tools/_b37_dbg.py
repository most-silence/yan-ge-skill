import importlib.util
spec = importlib.util.spec_from_file_location("b37", r"tools\_b37_blocks.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def show(eid, tss):
    lines = m.load_lines(eid)
    for ts in tss:
        for t, ln in lines:
            if t == ts:
                print(f"{eid} {ln}")
        print("-")
show("pp9CcfoGIEKl", ["00:16:09","00:16:11","00:16:14","00:16:15","00:16:18","00:16:19","00:16:22","00:16:25","00:16:26","00:16:28","00:16:29","00:16:31"])
show("UOVzuGdzs1dA", ["00:22:15","00:22:17","00:24:30","00:24:33","00:24:35","00:24:37","00:24:39","00:24:41"])
show("FW8NPflTV7gt", ["00:16:17","00:16:21","00:16:26","00:34:21","00:34:24","00:34:26","00:34:33","00:34:56","00:35:00","00:35:06"])
