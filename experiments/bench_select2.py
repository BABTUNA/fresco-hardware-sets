# round 3 page selection: fill per-book quotas and thin caveat tags
# targets come from raw text and page geometry, not from our parser
import json, os, re, random, collections
import pdfplumber
import pypdfium2 as pdfium
from finder import row_like
from lines import page_lines
from bench import result
from bench_tags import struck_words, drift

random.seed(31)
plan = json.load(open("eval/e2e_plan.json"))
labeled = {(f.split("_p")[0], int(f.split("_p")[1].split(".")[0])) for f in os.listdir("eval/gt")}
picked = collections.defaultdict(set)
MIN_PAGES = 5


def free(book, p):
    return (book, p) not in labeled and (book, p) not in picked and p not in plan[book]["dump_pages"]


def add(book, p, why):
    picked[(book, p)].add(why)


for b in plan:
    d = result("out_e2e", b)
    spec = json.load(open(d["spec"]))
    pages = d["pages"]
    pdf = pdfium.PdfDocument("../data/" + plan[b]["file"])
    texts = {p: [l.strip() for l in pdf[p].get_textpage().get_text_range().splitlines()] for p in pages}
    rows = {p: sum(row_like(l) for l in texts[p]) for p in pages}

    def take(cands, n, why):
        cands = [p for p in cands if free(b, p)]
        for p in random.sample(cands, min(n, len(cands))):
            add(b, p, why)

    # raw text targets
    take([p for p in pages if any(re.search(r"\b(NOT\s+USED|MOVED\s+TO)\b", l, re.I) for l in texts[p])], 6, "not_used")
    take([p for p in pages if any(re.match(r"\d{4}\s+[A-Za-z]", l) for l in texts[p])], 2, "four_digit_qty")
    take([p for p in pages if sum(bool(re.search(r"\s(Pemko|Sargent|Norton|Rockwood|McKinney|Hager|Ives|Schlage|LCN|Von Duprin)\s*$", l)) for l in texts[p]) >= 3], 3, "full_name_mfr")
    take([p for p in pages if sum(bool(re.match(r"(__+|--|As Req)\s", l, re.I)) for l in texts[p]) >= 2], 2, "blank_qty")
    # sets that cross a page break: the next page opens with component rows, not a header
    cross = [p for p in pages if p + 1 in texts and rows[p] >= 3 and any(row_like(l) for l in texts[p + 1][:8])]
    if cross:
        p = random.choice(cross)
        if free(b, p) and free(b, p + 1):
            add(b, p, "multi_page"); add(b, p + 1, "multi_page")
    # geometry targets: struck text and column drift, only on pages that have thin rules at all
    plb = pdfplumber.open("../data/" + plan[b]["file"])
    struck, drifted = [], []
    for p in pages:
        page = plb.pages[p]
        thin = [o for o in page.lines + page.rects if o["bottom"] - o["top"] < 2.5 and o["x1"] - o["x0"] > 4]
        lines = None
        if thin:
            lines = page_lines(page)
            if struck_words(page, lines) >= 2:
                struck.append(p)
        if spec.get("mode") != "grid" and rows[p] >= 3:
            lines = lines or page_lines(page)
            if drift(spec, lines) > 8:
                drifted.append(p)
    take(struck, 3, "struck_page")
    take(drifted, 3, "column_drift")
    # per-book quota, spread over the book's runs
    have = sum(1 for (bb, _) in labeled if bb == b) + sum(1 for (bb, _) in picked if bb == b)
    if have < MIN_PAGES:
        take([p for p in pages if rows[p] >= 2], MIN_PAGES - have, "book_quota")
    print(b, "struck pages:", len(struck), "drift pages:", len(drifted), flush=True)

# JC Ryan is the only book with centered cells, label more of it
d = result("out_e2e", "jcryan")
cands = [p for p in d["pages"] if free("jcryan", p)]
for p in random.sample(cands, min(5, len(cands))):
    add("jcryan", p, "centered_cells")

out = []
for (b, p), why in sorted(picked.items()):
    pdfplumber.open("../data/" + plan[b]["file"]).pages[p].to_image(resolution=130).save(f"eval/pages/{b}_p{p}.png")
    out.append({"book": b, "page": p, "targets": sorted(why)})
json.dump(out, open("eval/bench_pages_r3.json", "w"), indent=1)
print(len(out), "new pages")
print(collections.Counter(t for o in out for t in o["targets"]))
print(collections.Counter(o["book"] for o in out))
