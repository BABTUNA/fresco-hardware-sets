# list every field error, miss and extra on the benchmark pages, grouped by book
import json, os, re, glob, collections
import pdfplumber
from bench import result, plan
from score import align, norm, FIELDS

rows = collections.defaultdict(list)
for gt_file in sorted(glob.glob("eval/gt/*.json")):
    book, p = re.match(r"eval/gt/(\w+)_p(\d+)\.json", gt_file).groups()
    p = int(p)
    d = result(os.environ.get("OUT", "out_e2e"), book)
    gt = json.load(open(gt_file))
    gt_all = [c for s in gt["sets"] for c in s["components"]]
    ours = [c for s in d["sets"] for c in s["components"] if c.get("page") == p and c.get("status") != "removed"]
    pairs = align(gt_all, ours)
    mg, mo = {id(g) for g, _ in pairs}, {id(o) for _, o in pairs}
    for g, o in pairs:
        for f in FIELDS:
            gv, ov = (g.get(f), o.get(f)) if f == "qty" else (norm(g.get(f)), norm(o.get(f)))
            if gv != ov:
                rows[book].append(f"p{p} {f:11s} gt={str(gv)[:50]!r:52s} ours={str(ov)[:50]!r}")
    for g in gt_all:
        if id(g) not in mg: rows[book].append(f"p{p} MISSED      {g.get('qty')} | {g.get('description')} | {g.get('catalog')}")
    for o in ours:
        if id(o) not in mo: rows[book].append(f"p{p} EXTRA       {o.get('qty')} | {o.get('description')} | {o.get('catalog')}")
    sets_gt = {s["set_number"]: s.get("status", "active") for s in gt["sets"] if s.get("status", "active") != "active"}
    for sn, st in sets_gt.items():
        ours_s = [s for s in d["sets"] if s["set_number"].lstrip("0") == sn.lstrip("0") and any(l["page"] == p for l in s["location"])]
        if not ours_s or ours_s[0].get("status") != st:
            rows[book].append(f"p{p} STATUS      set {sn} gt={st} ours={ours_s[0].get('status') if ours_s else 'missing'}")
for b, rs in sorted(rows.items(), key=lambda x: -len(x[1])):
    print(f"## {b} ({len(rs)})")
    for r in (rs if os.environ.get("FULL") else rs[:14]): print("   ", r)
