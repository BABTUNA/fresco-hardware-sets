# page truth for the finder that does not come from the finder or from the pipeline output:
# a page with a printed set header (the broad reconcile pattern) is a set page, and a page sitting
# between two header pages at most 4 apart is a continuation. the finder is scored against that.
# usage: PYTHONPATH=. python layer1_truth.py
import json, collections
import pypdfium2 as pdfium
from reconcile import HEADERS, GRID
from finder import page_scores, runs

# pages the header rule picks up that are not set pages, checked by hand: four blank hfh pages that only
# carry the running header, and a foodservice page where "Hardware Group S52 Series" matched the pattern
NOT_SETS = {"hfh": {120, 163, 164, 165}, "livelle": {935}}


def header_truth(path):
    pdf = pdfium.PdfDocument(path)
    hp = []
    for i in range(len(pdf)):
        lines = pdf[i].get_textpage().get_text_range().splitlines()
        if any(rx.match(l) for l in lines for rx in HEADERS + [GRID]):
            hp.append(i)
    truth = set(hp)
    for a, b in zip(hp, hp[1:]):
        if 1 < b - a <= 4:
            truth.update(range(a + 1, b))
    return truth


def main():
    plan = json.load(open("eval/e2e_plan.json"))
    tot = collections.Counter()
    print(f"{'book':11s} {'truth':>5s} {'finder':>6s} {'+expand':>7s}  finder misses")
    for book, p in plan.items():
        path = "../data/" + p["file"]
        truth = header_truth(path) - NOT_SETS.get(book, set())
        s, v = page_scores(path)
        found = {i for a, b in runs(s, v) for i in range(a, b + 1)}
        expanded = set(json.load(open(f"out_e2e/{book}.json")).get("pages", []))
        tot["truth"] += len(truth); tot["found"] += len(found)
        tot["tp"] += len(found & truth); tot["tp2"] += len(expanded & truth)
        print(f"{book:11s} {len(truth):5d} {len(found & truth):6d} {len(expanded & truth):7d}  {sorted(truth - found)}")
    print(f"\nset pages by printed header: {tot['truth']}")
    print(f"finder alone:  {tot['tp']}/{tot['truth']} = {100 * tot['tp'] / tot['truth']:.1f}% recall, "
          f"{tot['tp']}/{tot['found']} = {100 * tot['tp'] / tot['found']:.1f}% precision")
    print(f"finder+expand: {tot['tp2']}/{tot['truth']} = {100 * tot['tp2'] / tot['truth']:.1f}% recall")


if __name__ == "__main__":
    main()
