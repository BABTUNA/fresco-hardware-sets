# exp 1b: right-aligned columns. same histogram but on word right edges (x1)
import sys, collections, pdfplumber
from books import BOOKS, path
from bands import qty_rows

for name in sys.argv[1:]:
    _, _, a, b = BOOKS[name]
    pdf = pdfplumber.open(path(name))
    rows = list(qty_rows(pdf, a, b))
    h0, h1 = collections.Counter(), collections.Counter()
    for l in rows:
        for b_ in {round(w["x0"] / 2) * 2 for w in l["words"]}: h0[b_] += 1
        for b_ in {round(w["x1"] / 2) * 2 for w in l["words"]}: h1[b_] += 1
    n = max(len(rows), 1)
    f = lambda h: "  ".join(f"{x}:{c/n:.0%}" for x, c in sorted(h.items()) if c >= 0.2 * n)
    print(f"{name:11s} rows={len(rows)}\n   left  {f(h0)}\n   right {f(h1)}")
    for l in rows[:4]: print("     |", l["text"][:110])
