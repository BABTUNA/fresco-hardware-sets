# sample page selection for the spec writer, two variants against the 2 densest pages:
#   p4  the 4 densest schedule pages
#   div pages picked for variety: start with the densest page, then keep adding the page that shows the most
#       header spellings and line shapes not seen yet, up to 4 pages
# usage: PYTHONPATH=. python sample_pages.py   writes dumps_p4/, dumps_div/ and eval/sample_plan.json
# the specs written from those dumps live in specs_sample/p4 and specs_sample/div
import json, os, re, collections
import pdfplumber
from finder import page_scores
from spec_parse import dump
from alt_induce import shape
from reconcile import HEADERS, GRID
from e2e import page_texts, D


def header_shapes(lines):
    # the wording before the set number: "hardware group/set" against "hardware groups/sets"
    return {re.sub(r"[#\d].*$", "", l.strip().lower()).strip() for l in lines if any(rx.match(l.strip()) for rx in HEADERS + [GRID])}


def pick_diverse(pages, texts, scores, cap=4):
    feats = {p: (header_shapes(texts[p]), {shape(l.strip()) for l in texts[p] if l.strip()}) for p in pages}
    chosen = [max(pages, key=lambda p: scores[p])]
    seen_h, seen_l = set(feats[chosen[0]][0]), set(feats[chosen[0]][1])
    while len(chosen) < min(cap, len(pages)):
        gain = lambda p: 10 * len(feats[p][0] - seen_h) + len(feats[p][1] - seen_l)
        best = max((p for p in pages if p not in chosen), key=lambda p: (gain(p), scores[p]))
        # the second page is always taken so every book gets at least the baseline's two
        if gain(best) == 0 and len(chosen) >= 2:
            break
        chosen.append(best)
        seen_h |= feats[best][0]; seen_l |= feats[best][1]
    return sorted(chosen)


def main():
    plan = json.load(open("eval/e2e_plan.json"))
    out = {}
    for d in ("dumps_p4", "dumps_div"):
        os.makedirs(d, exist_ok=True)
    for book, p in plan.items():
        path = D + p["file"]
        s, _ = page_scores(path)
        texts = page_texts(path)
        pages = [i for a, b in p["runs"] for i in range(a, b + 1)]
        p4 = sorted(sorted(pages, key=lambda i: s[i], reverse=True)[:4])
        div = pick_diverse(pages, texts, s)
        pdf = pdfplumber.open(path)
        open(f"dumps_p4/{book}.txt", "w").write(dump(pdf, p4))
        open(f"dumps_div/{book}.txt", "w").write(dump(pdf, div))
        out[book] = {"base": p["dump_pages"], "p4": p4, "div": div}
        nh = len(set().union(*(header_shapes(texts[i]) for i in pages)))
        print(f"{book:11s} base={p['dump_pages']}  p4={p4}  div={div}  header spellings in book={nh}", flush=True)
    json.dump(out, open("eval/sample_plan.json", "w"), indent=1)


if __name__ == "__main__":
    main()
