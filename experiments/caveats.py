# measure how often each caveat from the brief shows up in our extracted corpus
import json, glob, os, collections, re

def load():
    out = {}
    for f in sorted(glob.glob("out_e2e/*.json")):
        name = os.path.basename(f)
        if name.startswith("flags_") or ".r1" in name:
            continue
        b = name[:-5]
        r1 = f"out_e2e/{b}.r1.json"
        out[b] = json.load(open(r1 if os.path.exists(r1) else f))
    return out

def main():
    books = load()
    role = collections.defaultdict(lambda: collections.Counter())
    role_books = collections.defaultdict(lambda: collections.defaultdict(set))
    stats = collections.Counter()
    per_book = {}
    for b, d in books.items():
        sets = d["sets"]
        comps = [c for s in sets for c in s["components"]]
        for c in comps:
            for f in ("mfr", "finish"):
                v = (c.get(f) or "").strip().upper()
                if v and len(v) <= 6:
                    role[v][f] += 1
                    role_books[v][f].add(b)
        pb = {
            "sets": len(sets),
            "not_used": sum(s.get("status") == "not_used" for s in sets),
            "moved": sum(s.get("status") == "moved" for s in sets),
            "multi_page": sum(len({l["page"] for l in s["location"]}) > 1 for s in sets),
            "comps": len(comps),
            "qty_null": sum(c["qty"] is None for c in comps),
            "wrapped": sum((c["bbox"][3] - c["bbox"][1]) > 14 for c in comps),
        }
        # gap between consecutive sets on the same page, in points
        gaps = []
        for a, n in zip(sets, sets[1:]):
            la, ln = a["location"][-1], n["location"][0]
            if la["page"] == ln["page"]:
                gaps.append(round(ln["bbox"][1] - la["bbox"][3], 1))
        pb["tight_boundaries"] = sum(g < 8 for g in gaps)
        pb["same_page_boundaries"] = len(gaps)
        per_book[b] = pb
        stats.update(pb)

    print("== per book")
    print(f"{'book':11s} " + " ".join(f"{k:>10s}" for k in next(iter(per_book.values()))))
    for b, pb in per_book.items():
        print(f"{b:11s} " + " ".join(f"{v:10d}" for v in pb.values()))
    print(f"{'TOTAL':11s} " + " ".join(f"{stats[k]:10d}" for k in next(iter(per_book.values()))))

    print("\n== codes seen as BOTH mfr and finish (count as mfr / as finish, books)")
    both = [(v, r) for v, r in role.items() if r["mfr"] and r["finish"]]
    both.sort(key=lambda x: -(x[1]["mfr"] + x[1]["finish"]))
    for v, r in both[:25]:
        print(f"  {v:7s} mfr={r['mfr']:4d} in {sorted(role_books[v]['mfr'])}  finish={r['finish']:4d} in {sorted(role_books[v]['finish'])}")
    for v in ("PE", "NO", "A", "C", "B"):
        r = role.get(v, {})
        print(f"  focus {v}: mfr={r.get('mfr',0)} {sorted(role_books[v]['mfr'])} finish={r.get('finish',0)} {sorted(role_books[v]['finish'])}")

    print("\n== layout schemas")
    for b, d in books.items():
        s = json.load(open(d["spec"]))
        if s.get("mode") == "grid":
            print(f"  {b:11s} grid  {list(s['columns'].values())}")
        else:
            print(f"  {b:11s} {s.get('valign','top'):6s} {[c['field'] for c in sorted(s['columns'], key=lambda c: c['x'])]}")


if __name__ == "__main__":
    main()
