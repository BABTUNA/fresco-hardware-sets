# learn a book's column starts from its own repeated rows, then split rows into cells
import re, collections
from lines import page_lines

QTY = re.compile(r"^(\d{1,3}|__|--)$")

def qty_rows(pdf, a, b):
    for i in range(a, min(b, len(pdf.pages) - 1) + 1):
        for l in page_lines(pdf.pages[i]):
            if QTY.match(l["words"][0]["text"]) and len(l["words"]) >= 3:
                l["page"] = i
                yield l

def learn_bands(rows, min_share=0.5, merge=5):
    hist, n = collections.Counter(), 0
    for l in rows:
        n += 1
        for b in {round(w["x0"] / 2) * 2 for w in l["words"]}:
            hist[b] += 1
    peaks = sorted(x for x, c in hist.items() if c >= min_share * n)
    bands = []
    for x in peaks:
        if bands and x - bands[-1] <= merge:
            continue
        bands.append(x)
    return bands

def cells(line, bands, slack=3):
    out = [[] for _ in bands]
    for w in line["words"]:
        k = max((j for j, x in enumerate(bands) if x <= w["x0"] + slack), default=0)
        out[k].append(w["text"])
    return [" ".join(c) for c in out]
