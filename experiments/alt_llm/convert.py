# turn the per-page llm outputs into the scorer's result format and check every value against its cited lines
import json, glob, os, re, sys, collections
from score import norm

# usage: python alt_llm/convert.py [llm outputs dir] [results dir]
SRC = sys.argv[1] if len(sys.argv) > 1 else "alt_llm/out"
DST = sys.argv[2] if len(sys.argv) > 2 else "out_llm"

out = collections.defaultdict(list)
grounded = collections.Counter()
for f in sorted(glob.glob(f"{SRC}/*.json")):
    name = os.path.basename(f)[:-5]
    book, p = re.match(r"(\w+)_p(\d+)$", name).groups()
    p = int(p)
    lines = {}
    for l in open(f"alt_llm/input/{name}.txt"):
        m = re.match(r"L(\d+) (.*)", l.rstrip("\n"))
        if m:
            lines[int(m.group(1))] = re.sub(r"\[\d+\]", " ", m.group(2))
    try:
        d = json.load(open(f))
    except Exception as e:
        grounded["bad_json"] += 1
        continue
    for s in d.get("sets", []):
        starts = s.get("starts_on_page", True)
        comps = []
        for c in s.get("components", []):
            q = c.get("qty")
            cited = norm(" ".join(lines.get(int(i), "") for i in c.get("lines") or [] if str(i).isdigit())) or ""
            for fld in ("description", "catalog", "finish", "mfr"):
                v = norm(c.get(fld))
                if v:
                    grounded["values"] += 1
                    grounded["ok"] += all(t in cited for t in v.split())
            comps.append({"qty": q if isinstance(q, int) else None, "description": c.get("description"),
                          "catalog": c.get("catalog"), "finish": c.get("finish"), "mfr": c.get("mfr"), "page": p})
        out[book].append({"set_number": s.get("set_number") or "CONTINUED", "status": s.get("status", "active"),
                          "location": [{"page": p - 1}, {"page": p}] if not starts else [{"page": p}],
                          "components": comps})
os.makedirs(DST, exist_ok=True)
for book, sets in out.items():
    json.dump({"sets": sets}, open(f"{DST}/{book}.json", "w"))
print(f"{sum(len(v) for v in out.values())} sets, grounding: {grounded['ok']}/{grounded['values']} values found in their cited lines, bad json files: {grounded['bad_json']}")
