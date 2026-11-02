import json, sys, io
p = r"D:\Program Files\JianyingPro Drafts\10月22日 (1)\draft_content.json"
with io.open(p, "r", encoding="utf-8") as f:
    d = json.load(f)
print("top keys:", len(d))
for k in ("materials","tracks","canvas_config","duration"):
    if k in d:
        v = d[k]
        if isinstance(v, dict):
            print(f"  {k}: dict with keys -> {list(v.keys())}")
        elif isinstance(v, list):
            print(f"  {k}: list len={len(v)}")
        else:
            print(f"  {k}: {v}")
m = d.get("materials", {})
if isinstance(m, dict):
    print("\n== materials 子项 ==")
    for k, v in m.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} items")
t = d.get("tracks", [])
print("\n== tracks ==")
for tr in t:
    segs = tr.get("segments", [])
    print(f"  type={tr.get('type')} segments={len(segs)}")
