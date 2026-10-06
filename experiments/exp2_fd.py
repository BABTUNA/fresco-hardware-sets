# exp 2: the manufacturer column is a function of the catalog number; the finish column is not.
# for every short-code column, measure H(column | catalog stem). lowest = manufacturer.
import sys, math, collections, pdfplumber
from books import BOOKS, path
from bands import qty_rows, learn_bands, cells

def cond_entropy(pairs):
    by = collections.defaultdict(collections.Counter)
    for k, v in pairs: by[k][v] += 1
    n = len(pairs); h = 0.0
    for c in by.values():
        t = sum(c.values())
        h += t / n * -sum(m / t * math.log2(m / t) for m in c.values())
    return h

for name in (sys.argv[1:] or BOOKS):
    _, _, a, b = BOOKS[name]
    pdf = pdfplumber.open(path(name))
    rows = list(qty_rows(pdf, a, b))
    if len(rows) < 20:
        print(f"{name:11s} too few rows ({len(rows)})"); continue
    bands = learn_bands(rows)
    if len(bands) < 3:
        print(f"{name:11s} bands={bands} (layout not columnar)"); continue
    table = [cells(l, bands) for l in rows]
    # short-code columns: mostly a single short token
    code_cols = [j for j in range(2, len(bands))
                 if sum(1 for r in table if r[j] and len(r[j].split()) == 1 and len(r[j]) <= 6) >= 0.6 * len(table)]
    if len(code_cols) < 2:
        print(f"{name:11s} bands={bands} code columns={code_cols} (need 2)"); continue
    cat = code_cols[0] - 1
    res = []
    for j in code_cols:
        pairs = [(r[cat].split()[0], r[j]) for r in table if r[cat] and r[j]]
        vals = collections.Counter(r[j] for r in table if r[j])
        res.append((cond_entropy(pairs), j, vals.most_common(4)))
    res.sort()
    print(f"{name:11s} rows={len(rows):4d} catalog=col{cat}")
    for h, j, top in res:
        print(f"      col{j} x={bands[j]:<4} H(col|catalog)={h:.3f}  top={top}")
