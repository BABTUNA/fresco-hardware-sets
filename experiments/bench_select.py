# pick benchmark pages so every caveat and every page run is covered
# targets come from raw text where possible, so the selection does not depend on our parser
import json, re, random, collections
import pdfplumber
import pypdfium2 as pdfium
from caveats import load

random.seed(23)
plan = json.load(open("eval/e2e_plan.json"))
books = load()
labeled = {(f.split("_p")[0], int(f.split("_p")[1].split(".")[0]))
           for f in __import__("os").listdir("eval/gt")}

TARGETS = {
    "not_used": re.compile(r"\b(NOT\s+USED|MOVED\s+TO)\b", re.I),
    "ambiguous_code": re.compile(r"\s(PE|NO|A|AA|C|B|BK|SC|IV|LC|TR|PB|MC|RO)\s*$"),
    "blank_qty": re.compile(r"^\s*(__+|--|As Req)\s", re.I),
}
picked = collections.defaultdict(set)


def add(book, page, why):
    if (book, page) not in labeled:
        picked[(book, page)].add(why)


for b, d in books.items():
    pdf = pdfium.PdfDocument("../data/" + plan[b]["file"])
    pages = d["pages"]
    texts = {p: pdf[p].get_textpage().get_text_range().splitlines() for p in pages}
    # raw text targets, at most 2 pages per caveat per book
    for tag, rx in TARGETS.items():
        hits = [p for p in pages if sum(bool(rx.search(l)) for l in texts[p]) >= 1]
        for p in random.sample(hits, min(2 if tag != "ambiguous_code" else 1, len(hits))):
            add(b, p, tag)
    # every page run gets at least one page
    runs = [r for r in plan[b]["runs"]]
    for a, z in runs:
        in_run = [p for p in pages if a <= p <= z]
        if in_run and not any((b, p) in labeled or (b, p) in picked for p in in_run):
            add(b, random.choice(in_run), "run_coverage")
    # a set that crosses a page break: label both pages
    multi = [s for s in d["sets"] if len({l["page"] for l in s["location"]}) > 1]
    if multi:
        s = random.choice(multi)
        p0 = s["location"][0]["page"]
        add(b, p0, "multi_page"); add(b, p0 + 1, "multi_page")
    # many sets on one page means tight boundaries
    per_page = collections.Counter(s["location"][0]["page"] for s in d["sets"])
    dense = [p for p, n in per_page.items() if n >= 4]
    if dense:
        add(b, random.choice(dense), "dense_boundaries")

# render and write the list
out = []
for (b, p), why in sorted(picked.items()):
    pdfplumber.open("../data/" + plan[b]["file"]).pages[p].to_image(resolution=130).save(f"eval/pages/{b}_p{p}.png")
    out.append({"book": b, "page": p, "targets": sorted(why)})
json.dump(out, open("eval/bench_pages.json", "w"), indent=1)
print(len(out), "new pages")
print(collections.Counter(t for o in out for t in o["targets"]))
for o in out:
    print(f"  {o['book']}_p{o['page']}: {o['targets']}")
