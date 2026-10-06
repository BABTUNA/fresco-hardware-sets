# caveat benchmark: exact scoring of every labeled set and row, reported per caveat and per difficulty tier
# usage: python bench.py [results dir]   (default out_e2e, picks <book>.r1.json when present)
import json, os, re, sys, glob, collections
# GT=eval/holdout/gt scores a held-out label set; tags are frozen next to it
GT = os.environ.get("GT", "eval/gt")
TAGS = "eval/tags.json" if GT == "eval/gt" else GT + "/../tags.json"
from score import norm, norm_set, FIELDS

plan = json.load(open("eval/e2e_plan.json"))


def result(results_dir, book):
    r1 = f"{results_dir}/{book}.r1.json"
    return json.load(open(r1 if os.path.exists(r1) else f"{results_dir}/{book}.json"))


def load_tags():
    if not os.path.exists(TAGS):
        sys.exit("eval/tags.json missing, run bench_tags.py first")
    return json.load(open(TAGS))["pages"]


def row(c):
    # a row is right only if every field matches exactly, after normalizing text
    return tuple(c.get(f) if f == "qty" else norm(c.get(f)) for f in FIELDS)


def group_key(set_number, starts_here):
    # rows are compared inside the same set; a set carried over from an earlier page
    # is matched to whatever set we carried over onto this page
    return ("set", norm_set(set_number)) if starts_here else ("continued",)


def score_group(gt_comps, ours):
    # exact multiset matching inside one set: no similarity scores, no cutoffs, no row order
    left_rows = collections.Counter(row(o) for o in ours)
    left_vals = {f: collections.Counter(row(o)[i] for o in ours) for i, f in enumerate(FIELDS)}
    our_mfr = {norm(o.get("mfr")) for o in ours} - {None}
    our_fin = {norm(o.get("finish")) for o in ours} - {None}
    out = []
    for g in gt_comps:
        r = row(g)
        res = {"exact": left_rows[r] > 0}
        if res["exact"]:
            left_rows[r] -= 1
        for i, f in enumerate(FIELDS):
            res[f] = left_vals[f][r[i]] > 0
            if res[f]:
                left_vals[f][r[i]] -= 1
        gm, gf = norm(g.get("mfr")), norm(g.get("finish"))
        res["swap"] = bool((gm and not res["mfr"] and gm in our_fin) or (gf and not res["finish"] and gf in our_mfr))
        out.append(res)
    return out


def main(results_dir="out_e2e"):
    by_tag = collections.defaultdict(collections.Counter)
    sets_tag = collections.defaultdict(collections.Counter)
    prec = collections.Counter()
    misses = []
    full = collections.defaultdict(lambda: [0, 0])
    frozen = load_tags()
    for gt_file in sorted(glob.glob(GT + "/*.json")):
        book, page_no = re.match(r".*/(\w+)_p(\d+)\.json", gt_file).groups()
        page_no = int(page_no)
        if book not in plan:
            continue
        d = result(results_dir, book)
        gt = json.load(open(gt_file))
        key = f"{book}_p{page_no}"
        ft = frozen.get(key)
        # tags are frozen against the labels, so an edited label file needs a fresh freeze
        if ft is None or [len(s["components"]) for s in ft["sets"]] != [len(s["components"]) for s in gt["sets"]] or \
                any(fc["description"] != c.get("description") for fs, s in zip(ft["sets"], gt["sets"]) for fc, c in zip(fs["components"], s["components"])):
            sys.exit(f"{key} changed since tags were frozen, rerun bench_tags.py")
        # pages the spec writer saw are reported separately so they cannot flatter the headline
        seen = ft["seen_by_spec_writer"]

        # our sets and rows on this page, grouped the same way as the labels
        our_sets = collections.defaultdict(list)
        our_rows = collections.defaultdict(list)
        for s in d["sets"]:
            pages = [l["page"] for l in s["location"]]
            if page_no not in pages:
                continue
            k = group_key(s["set_number"], min(pages) == page_no)
            our_sets[k].append(s)
            our_rows[k] += [c for c in s["components"] if c.get("page") == page_no and c.get("status") != "removed"]
        gt_rows = collections.defaultdict(list)
        for s, fs in zip(gt["sets"], ft["sets"]):
            starts = s.get("starts_on_page", True)
            k = group_key(s["set_number"], starts)
            for c, fc in zip(s["components"], fs["components"]):
                c["_tags"], c["_tier"] = set(fc["tags"]), fc["tier"]
                gt_rows[k].append(c)
            if not starts:
                continue
            # set level: found by set number on this page, and NOT USED / moved status
            status = s.get("status", "active")
            ours = our_sets.get(k, [None])[0]
            for t in set(fs["tags"]) | {"ALL"}:
                sets_tag[t]["gt"] += 1
                sets_tag[t]["found"] += ours is not None
                if status != "active":
                    sets_tag[t]["status_n"] += 1
                    sets_tag[t]["status_ok"] += ours is not None and ours.get("status") == status
            if ours is None:
                misses.append({"page": key, "kind": "set", "set": s["set_number"], "tags": sorted(fs["tags"])})

        # row level, one set at a time
        prec["ours"] += sum(len(v) for v in our_rows.values())
        group_ok = {}
        for k, gcs in gt_rows.items():
            results = score_group(gcs, our_rows.get(k, []))
            # a set is fully right when every labeled row is exact and we added nothing to it
            group_ok[k] = all(r["exact"] for r in results) and len(our_rows.get(k, [])) == len(gcs)
            for g, res in zip(gcs, results):
                prec["exact"] += res["exact"]
                buckets = g["_tags"] | {"ALL", g["_tier"], f"book:{book}"} | (set() if seen else {"ALL unseen pages"})
                for t in buckets:
                    b = by_tag[t]
                    b["n"] += 1
                    b["exact"] += res["exact"]
                    b["swaps"] += res["swap"]
                    for f in FIELDS:
                        b[f] += res[f]
                if not res["exact"]:
                    misses.append({"page": key, "kind": "row", "description": g.get("description"),
                                   "wrong": [f for f in FIELDS if not res[f]], "tags": sorted(g["_tags"])})
        for s, fs in zip(gt["sets"], ft["sets"]):
            starts = s.get("starts_on_page", True)
            k = group_key(s["set_number"], starts)
            status = s.get("status", "active")
            ours = our_sets.get(k, [None])[0] if starts else True
            ok = ours is not None and group_ok.get(k, not our_rows.get(k)) and (status == "active" or ours.get("status") == status)
            kind = "sets" if starts else "continued pieces"
            for b in ("ALL", f"book:{book}") + (() if seen else ("ALL unseen pages",)):
                full[(kind, b)][0] += 1
                full[(kind, b)][1] += bool(ok)

    pct = lambda a, b: f"{100 * a / b:5.1f}" if b else "    -"
    order = ["ALL", "ALL unseen pages", "T0 trivial", "T1 one caveat", "T2 hard"]
    rest = sorted(t for t in by_tag if t not in order and not t.startswith("book:"))
    books = sorted(t for t in by_tag if t.startswith("book:"))
    head = f"{'n':>5s} {'exact':>6s} " + " ".join(f"{f[:6]:>6s}" for f in FIELDS) + "  swaps"
    line = lambda name, b: f"{name:22s} {b['n']:5d} {pct(b['exact'], b['n']):>6s} " + " ".join(f"{pct(b[f], b['n']):>6s}" for f in FIELDS) + f"  {b['swaps']:5d}"
    print(f"{'rows by caveat':22s} {head}")
    for t in order + [""] + rest:
        print(line(t, by_tag[t]) if t else "")
    avg = sum(by_tag[t]["exact"] / by_tag[t]["n"] for t in books) / len(books)
    print(f"{'per-book average':22s} {len(books):5d} {100 * avg:6.1f}")
    print(f"\n{'rows by book':22s} {head}")
    for t in books:
        print(line("  " + t[5:], by_tag[t]))
    print(f"\n{'sets by caveat':22s} {'n':>5s} {'found':>6s} {'status':>7s}")
    for t in ["ALL"] + sorted(x for x in sets_tag if x != "ALL"):
        b = sets_tag[t]
        print(f"{t:22s} {b['gt']:5d} {pct(b['found'], b['gt']):>6s} {pct(b['status_ok'], b['status_n']):>7s}")
    print(f"\n{'sets fully correct':22s} {'n':>5s} {'right':>6s}")
    for kind in ("sets", "continued pieces"):
        for b in ("ALL", "ALL unseen pages"):
            n, ok = full[(kind, b)]
            print(f"{kind + (' (unseen pages)' if b != 'ALL' else ''):34s} {n:5d} {pct(ok, n):>6s}")
    worst = sorted((full[("sets", t)][1] / full[("sets", t)][0], t[5:], full[("sets", t)][0]) for t in books if full[("sets", t)][0])
    print("  per book: " + ", ".join(f"{b} {100 * r:.0f}% of {n}" for r, b, n in worst))
    print(f"\nrow precision: {prec['exact']}/{prec['ours']} = {pct(prec['exact'], prec['ours'])}% of our rows on labeled pages are exactly right")
    json.dump(misses, open("eval/bench_misses.json", "w"), indent=1)
    print(f"{len(misses)} misses written to eval/bench_misses.json")


if __name__ == "__main__":
    main(*sys.argv[1:])
