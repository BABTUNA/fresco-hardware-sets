# pick, per test book: the schedule page range, 2 dump pages for the spec writer,
# and 2 different ground-truth pages rendered as images for an independent labeler
import re, json, random, os
import pdfplumber
from books import BOOKS, path
from lines import page_lines
from spec_parse import dump

HDR = re.compile(r"(HARDWARE GROUP|HARDWARE SET|Hardware Group|Set\s*[#:]|Heading #|^\d+\.\d+\s)", re.I)
QTY = re.compile(r"^(\d{1,3}|__|--)$")
TEST = ["hfh", "valor", "livelle", "usi", "sat", "doorco", "jcryan", "morris", "roselle"]
random.seed(7)
os.makedirs("eval/pages", exist_ok=True)
plan = {}
for name in TEST:
    _, _, a, b = BOOKS[name]
    pdf = pdfplumber.open(path(name))
    b = min(b, len(pdf.pages) - 1)
    score = {}
    for i in range(a, b + 1):
        ls = page_lines(pdf.pages[i])
        h = sum(1 for l in ls if HDR.search(l["text"]))
        q = sum(1 for l in ls if QTY.match(l["words"][0]["text"]))
        if h:
            score[i] = q + 3 * h
    pages = sorted(score)
    lo, hi = pages[0], pages[-1]
    ranked = sorted(score, key=score.get, reverse=True)
    dump_pages = sorted(ranked[:2])
    rest = [p for p in pages if p not in dump_pages and score[p] >= 8]
    gt_pages = sorted(random.sample(rest, min(2, len(rest))))
    open(f"dumps/{name}.txt", "w").write(dump(pdf, dump_pages))
    for p in gt_pages:
        pdf.pages[p].to_image(resolution=130).save(f"eval/pages/{name}_p{p}.png")
    plan[name] = {"range": [lo, hi], "dump_pages": dump_pages, "gt_pages": gt_pages}
    print(name, plan[name])
json.dump(plan, open("eval/plan.json", "w"), indent=1)
