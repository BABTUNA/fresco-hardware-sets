# does the pipeline find every hardware set in each book?
# scans every page of every book for header-shaped lines with one broad pattern, independent of
# our specs and page finder, and compares those set numbers with the sets we extracted
# usage: python reconcile.py [results dir]
import json, re, sys, collections
import pypdfium2 as pdfium
from bench import result, plan
from score import norm_set

ID = r"(?P<num>(?:[A-Z]{1,5}[ -]?)?\d[\w.\-]*(?: \d[\w.\-]*)?|MISC\b)"
HEADERS = [
    re.compile(rf"^\s*(?:PART\s+\d+\s*-\s*)?hardware\s+(?:group|set)s?(?:\s*/\s*(?:group|set)s?)?\s*(?:no\.?|number)?\s*[#:]?\s*{ID}", re.I),
    re.compile(rf"^\s*set\s*[#:]\s*{ID}", re.I),
    re.compile(rf"^\s*HW\s+{ID}"),
    re.compile(rf"^\s*heading\s*#\s*{ID}", re.I),
]
# grid schedules (roselle) put the set number at the start of a row that has a "MFR - PRODUCT" cell
GRID = re.compile(r"^\s*(?P<num>\d{1,2}\.\d{1,2})\s+[A-Z].*\s-\s.*\b6\d\d\b")


def pdf_headers(path):
    pdf = pdfium.PdfDocument(path)
    found = collections.defaultdict(list)
    for i in range(len(pdf)):
        for line in pdf[i].get_textpage().get_text_range().splitlines():
            for rx in HEADERS + [GRID]:
                m = rx.match(line)
                if m:
                    found[norm_set(m.group("num").rstrip(".:"))].append((i, line.strip()[:90]))
                    break
    return found


def main(results_dir="out_e2e"):
    rows, tot = [], collections.Counter()
    for book, p in plan.items():
        pdf_sets = pdf_headers("../data/" + p["file"])
        ours = {norm_set(s["set_number"]) for s in result(results_dir, book)["sets"]}
        missing = sorted(set(pdf_sets) - ours)
        extra = sorted(ours - set(pdf_sets))
        lines = sum(len(v) for v in pdf_sets.values())
        tot["pdf"] += len(pdf_sets); tot["found"] += len(set(pdf_sets) & ours); tot["ours"] += len(ours)
        rows.append((book, lines, len(pdf_sets), len(ours), len(set(pdf_sets) & ours), missing, extra, pdf_sets))
    print(f"{'book':11s} {'header lines':>12s} {'pdf sets':>8s} {'ours':>5s} {'matched':>7s}  missing from ours / extra in ours")
    for book, lines, n_pdf, n_ours, n_both, missing, extra, pdf_sets in rows:
        print(f"{book:11s} {lines:12d} {n_pdf:8d} {n_ours:5d} {n_both:7d}  "
              f"missing={len(missing)} extra={extra[:6]}")
    print(f"\nTOTAL: {tot['found']}/{tot['pdf']} set numbers printed in the PDFs are in our output "
          f"({100 * tot['found'] / tot['pdf']:.1f}%); we output {tot['ours']} distinct set numbers")
    for book, *_, missing, extra, pdf_sets in rows:
        for m in missing:
            print(f"  MISSING {book:10s} {m:8s} {pdf_sets[m][:2]}")
    json.dump([{"book": r[0], "missing": {m: r[7][m] for m in r[5]}, "extra": r[6]} for r in rows], open("eval/reconcile.json", "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:])
