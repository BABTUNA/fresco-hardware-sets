# pass/fail unit checks for each caveat in the brief, expectations taken from the raw PDF text
# usage: python bench_checks.py [results dir]
import json, re, sys, collections
from bench import result
from score import norm, norm_set
from finder import page_scores, runs


def find_sets(d, chk):
    out = [s for s in d["sets"] if "set" not in chk or norm_set(s["set_number"]) == norm_set(chk["set"])]
    if "page" in chk:
        out = [s for s in out if any(l["page"] == chk["page"] for l in s["location"])]
    return out


def run_check(chk, d):
    sets = find_sets(d, chk)
    comps = [c for s in sets for c in s["components"] if c.get("status") != "removed"]
    if "absent" in chk:
        pool = comps if "set" in chk else [c for s in d["sets"] for c in s["components"] if c.get("status") != "removed"]
        hits = [c["description"] for c in pool if re.search(chk["absent"], c.get("description") or "", re.I)]
        return not hits, f"found {len(hits)}: {hits[:2]}"
    if not sets:
        return False, "set not found"
    if chk.get("exists"):
        return True, ""
    if "status" in chk:
        s = sets[0]
        ok = s.get("status") == chk["status"] and (chk.get("moved_to") is None or s.get("moved_to") == chk["moved_to"])
        return ok, f"status={s.get('status')} moved_to={s.get('moved_to')}"
    if "count" in chk:
        return len(comps) == chk["count"], f"{len(comps)} components"
    if "pages" in chk:
        pages = sorted({l["page"] for s in sets for l in s["location"]})
        return all(p in pages for p in chk["pages"]), f"pages={pages}"
    if "page" in chk and "set" not in chk:
        comps = [c for c in comps if c.get("page") == chk["page"]]
    c = next((c for c in comps if re.search(chk["desc"], c.get("description") or "", re.I)), None)
    if c is None:
        return False, "component not found"
    bad = {k: c.get(k) for k, v in chk["expect"].items()
           if (c.get(k) != v if k == "qty" else norm(c.get(k)) != norm(v))}
    return not bad, f"got {bad}" if bad else ""


def main(results_dir="out_e2e"):
    checks = json.load(open("eval/checks.json"))
    cache, by_caveat, rows = {}, collections.defaultdict(lambda: [0, 0]), []
    for chk in checks:
        if chk["book"] not in cache:
            cache[chk["book"]] = result(results_dir, chk["book"])
        ok, why = run_check(chk, cache[chk["book"]])
        by_caveat[chk["caveat"]][0] += ok
        by_caveat[chk["caveat"]][1] += 1
        rows.append((chk["caveat"], chk["id"], ok, why))
    # books with no hardware sets must come back empty
    for rel in json.load(open("eval/negatives.json")):
        s, v = page_scores("../data/" + rel)
        r = runs(s, v)
        by_caveat["no_sets_book"][0] += not r
        by_caveat["no_sets_book"][1] += 1
        rows.append(("no_sets_book", rel.split("/")[-1][:22], not r, f"runs {r}"))
    for cav, cid, ok, why in rows:
        print(f"  {'PASS' if ok else 'FAIL'}  {cav:15s} {cid:22s} {'' if ok else why}")
    print()
    for cav, (p, n) in by_caveat.items():
        print(f"  {cav:15s} {p}/{n}")
    total = sum(p for p, _ in by_caveat.values())
    print(f"  {'TOTAL':15s} {total}/{len(rows)}")


if __name__ == "__main__":
    main(*sys.argv[1:])
