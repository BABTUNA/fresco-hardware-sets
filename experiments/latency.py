# wall-clock for the deterministic parts of the pipeline, per book: the page finder over the whole PDF,
# and the interpreter over the set pages with the book's spec. the model calls are estimated separately
# from measured token counts, see APPROACH_RESULTS.md
# usage: PYTHONPATH=. python latency.py
import json, os, time
import pdfplumber
import pypdfium2 as pdfium
from finder import page_scores, runs
from spec_parse import run
from e2e import page_texts, expand_pages, D


def main():
    plan = json.load(open("eval/e2e_plan.json"))
    tot = {"pages": 0, "set_pages": 0, "finder": 0.0, "interp": 0.0}
    print(f"{'book':11s} {'pages':>6s} {'set pg':>6s} {'finder s':>9s} {'interp s':>9s}")
    for book, p in plan.items():
        path = D + p["file"]
        t = time.time()
        s, v = page_scores(path)
        r = runs(s, v)
        finder = time.time() - t
        spec_file = f"specs_e2e/{book}.r1.json"
        if not os.path.exists(spec_file):
            spec_file = f"specs_e2e/{book}.json"
        spec = json.load(open(spec_file))
        t = time.time()
        pages = expand_pages(spec, page_texts(path), r)
        run(spec, pdfplumber.open(path), pages)
        interp = time.time() - t
        n = len(pdfium.PdfDocument(path))
        tot["pages"] += n; tot["set_pages"] += len(pages); tot["finder"] += finder; tot["interp"] += interp
        print(f"{book:11s} {n:6d} {len(pages):6d} {finder:9.1f} {interp:9.1f}", flush=True)
    print(f"{'TOTAL':11s} {tot['pages']:6d} {tot['set_pages']:6d} {tot['finder']:9.1f} {tot['interp']:9.1f}")


if __name__ == "__main__":
    main()
