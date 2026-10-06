# how often two independent labelers agree on the same page, field by field
import json, glob, os, collections
from score import align, norm, norm_set, FIELDS

tot = collections.Counter()
for f2 in sorted(glob.glob("eval/gt2/*.json")):
    f1 = "eval/gt/" + os.path.basename(f2)
    a, b = json.load(open(f1)), json.load(open(f2))
    sa = {norm_set(s["set_number"]): s.get("status", "active") for s in a["sets"] if s.get("starts_on_page", True)}
    sb = {norm_set(s["set_number"]): s.get("status", "active") for s in b["sets"] if s.get("starts_on_page", True)}
    ca = [c for s in a["sets"] for c in s["components"]]
    cb = [c for s in b["sets"] for c in s["components"]]
    pairs = align(ca, cb)
    tot["sets_union"] += len(set(sa) | set(sb)); tot["sets_both"] += len(set(sa) & set(sb))
    tot["comps_max"] += max(len(ca), len(cb)); tot["comps_paired"] += len(pairs)
    diffs = []
    for x, y in pairs:
        for fld in FIELDS:
            vx, vy = (x.get(fld), y.get(fld)) if fld == "qty" else (norm(x.get(fld)), norm(y.get(fld)))
            tot[fld] += vx == vy
            if vx != vy:
                diffs.append(f"{fld}: {str(vx)[:40]!r} vs {str(vy)[:40]!r}")
    print(f"{os.path.basename(f2):22s} sets {len(sa)}/{len(sb)}  comps {len(ca)}/{len(cb)} paired {len(pairs)}  field diffs {len(diffs)}")
    for d in diffs[:4]:
        print("      ", d)
pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "-"
print(f"\nset agreement {pct(tot['sets_both'], tot['sets_union'])}, component agreement {pct(tot['comps_paired'], tot['comps_max'])}")
print("field agreement on paired components: " + ", ".join(f"{f} {pct(tot[f], tot['comps_paired'])}" for f in FIELDS))
