# run every sample book through hwsets with the checked-in specs, no API calls, and write the results
# in the shape bench.py reads (0-based pages, "catalog" field) to out_hwsets/, and the viewer's copy to out/
# usage: from the repo root, uv run python experiments/run_hwsets.py
import json, os, sys, time
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R); os.chdir(R)
from hwsets.extract import extract_book, spec_name
plan = json.load(open("experiments/eval/e2e_plan.json"))
os.makedirs("experiments/out_hwsets", exist_ok=True); os.makedirs("out", exist_ok=True)
for book, p in plan.items():
    t = time.time()
    r = extract_book("data/" + p["file"], allow_llm=False)
    json.dump(r, open(f"out/{book}.json", "w"), indent=1)
    # the viewer reads out/<spec id>.json, so a batch run refreshes what it shows
    r["id"] = spec_name("data/" + p["file"])
    json.dump(r, open(f"out/{r['id']}.json", "w"), indent=1)
    old = {"sets": [{**s, "location": [{"page": l["page"] - 1, "bbox": l["bbox"]} for l in s["location"]],
                     "components": [{**c, "catalog": c["catalog_number"], "page": c["page"] - 1} for c in s["components"]]} for s in r["sets"]]}
    json.dump(old, open(f"experiments/out_hwsets/{book}.json", "w"))
    n = sum(len(s["components"]) for s in r["sets"])
    print(f"{book:11s} {r['status']:13s} sets={len(r['sets']):4d} comps={n:5d} flags={[f['check'] for f in r['flags']]} {time.time()-t:5.1f}s", flush=True)
