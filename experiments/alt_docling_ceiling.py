# best case for docling + an llm column mapper: a labeled row only counts if docling put it in one
# table row with its catalog, finish and mfr each sitting alone in a cell
import json, glob, re, sys, collections
from score import norm
tables = json.load(open(sys.argv[1]))
MERGE = len(sys.argv) > 2 and sys.argv[2] == "merge"
tot = collections.Counter()
by_book = collections.defaultdict(collections.Counter)
for f in sorted(glob.glob("eval/gt/*.json")):
    key = re.search(r"(\w+_p\d+)\.json", f).group(1)
    if key not in tables:
        continue
    book = key.split("_p")[0]
    rows = []
    for t in tables[key]:
        merged = []
        for r in t:
            cells = [(c or "").replace("\n", " ").strip() for c in r]
            first = next((c for c in cells if c), "")
            # a grid row with no quantity in front continues the row above (a wrapped cell)
            if MERGE and merged and not re.match(r"^(\d{1,4}(\.0)?|_+|--)\b", first):
                merged[-1] = [" ".join(filter(None, [a, b])) for a, b in zip(merged[-1], cells + [""] * (len(merged[-1]) - len(cells)))]
            else:
                merged.append(cells)
        rows += [[norm(c) or "" for c in r] for r in merged]
    tot["pages"] += 1
    tot["pages_with_tables"] += bool(tables[key])
    for s in json.load(open(f))["sets"]:
        for c in s["components"]:
            want = [norm(c.get(k)) for k in ("catalog", "finish", "mfr") if c.get(k)]
            ok = any(all(w in r for w in want) for r in rows) if want else False
            tot["n"] += 1; tot["ok"] += ok
            by_book[book]["n"] += 1; by_book[book]["ok"] += ok
print(f"pages scored {tot['pages']}, pages where docling found any table: {tot['pages_with_tables']}")
print(f"ceiling: {tot['ok']}/{tot['n']} = {100 * tot['ok'] / tot['n']:.1f}% of labeled rows recovered as one clean table row")
for b, c in sorted(by_book.items()):
    print(f"  {b:11s} {100 * c['ok'] / c['n']:5.1f}%  of {c['n']}")
