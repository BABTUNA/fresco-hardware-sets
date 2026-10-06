# are the labels themselves right? every labeled code should appear in the page's own text layer
import json, glob, re, collections
import pdfplumber
from lines import page_lines
from bench import plan
from score import norm

tot = collections.Counter()
bad = []
pdfs = {}
for f in sorted(glob.glob("eval/gt/*.json")):
    book, p = re.match(r"eval/gt/(\w+)_p(\d+)\.json", f).groups()
    p = int(p)
    if book not in plan:
        continue
    pdfs.setdefault(book, pdfplumber.open("../data/" + plan[book]["file"]))
    text = norm(" ".join(l["text"] for l in page_lines(pdfs[book].pages[p]))) or ""
    toks = set(text.split())
    for s in json.load(open(f))["sets"]:
        for c in s["components"]:
            for fld in ("catalog", "finish", "mfr"):
                v = norm(c.get(fld))
                if not v:
                    continue
                tot[fld] += 1
                missing = [t for t in v.split() if t not in toks and t not in text]
                if missing:
                    bad.append((f"{book}_p{p}", fld, c.get(fld), missing))
                else:
                    tot[fld + "_ok"] += 1
for fld in ("catalog", "finish", "mfr"):
    print(f"{fld:8s} {tot[fld + '_ok']}/{tot[fld]} label values found in the page text")
print(f"\n{len(bad)} labeled values with words not in the text layer:")
for b in bad:
    print("  ", b)
