# print every field mismatch and unmatched component for one book
import json, re, sys, glob, collections
import pdfplumber
from books import path
from spec_parse import run
from score import align, norm, norm_set, FIELDS

name, prefix = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "oneshot_")
plan = json.load(open("eval/plan.json"))[name]
pdf = pdfplumber.open(path(name))
sets = run(json.load(open(f"specs/{prefix}{name}.json")), pdf, range(plan["range"][0], plan["range"][1] + 1))
for gt_file in sorted(glob.glob(f"eval/gt/{name}_p*.json")):
    page = int(re.search(r"_p(\d+)\.json$", gt_file).group(1))
    gt = json.load(open(gt_file))
    ours = [c for s in sets for c in s["components"] if c.get("page") == page]
    gt_all = [c for s in gt["sets"] for c in s["components"]]
    print(f"== page {page}: gt sets {[s['set_number'] for s in gt['sets']]} | our sets {[s['set_number'] for s in sets if any(l['page']==page for l in s['location'])]}")
    pairs = align(gt_all, ours)
    for g, o in pairs:
        for f in FIELDS:
            gv, ov = (g.get(f), o.get(f)) if f == "qty" else (norm(g.get(f)), norm(o.get(f)))
            if gv != ov:
                print(f"   {f:11s} gt={gv!r:45.45s} ours={ov!r}")
    mg = {id(g) for g, _ in pairs}; mo = {id(o) for _, o in pairs}
    for g in gt_all:
        if id(g) not in mg: print("   MISSED", {k: g.get(k) for k in FIELDS})
    for o in ours:
        if id(o) not in mo: print("   EXTRA ", {k: o.get(k) for k in FIELDS})
