# exp 1: do component rows share stable column start positions across a whole book?
# for every line that starts with a quantity, histogram the x0 of each word (2pt bins).
# sharp peaks = left-aligned columns. report peaks holding >=15% of rows.
import re, sys, collections, pdfplumber
from books import BOOKS, path
from lines import page_lines

QTY = re.compile(r"^(\d{1,3}|__|--)$")
for name in (sys.argv[1:] or BOOKS):
    _, _, a, b = BOOKS[name]
    pdf = pdfplumber.open(path(name))
    hist, nrows = collections.Counter(), 0
    for i in range(a, b + 1):
        for l in page_lines(pdf.pages[i]):
            if QTY.match(l["words"][0]["text"]) and len(l["words"]) >= 3:
                nrows += 1
                seen = set()
                for w in l["words"]:
                    bin_ = round(w["x0"] / 2) * 2
                    if bin_ not in seen:
                        hist[bin_] += 1; seen.add(bin_)
    peaks = sorted((x, c) for x, c in hist.items() if c >= 0.15 * nrows)
    print(f"{name:11s} rows={nrows:4d}  column starts (x:share) " +
          "  ".join(f"{x}:{c/nrows:.0%}" for x, c in peaks))
