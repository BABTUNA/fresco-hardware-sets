# end to end: finder ranges -> compiled spec -> interpreter -> audit -> score against image labels
# usage: python e2e.py [spec suffix]   e.g. "" for specs_e2e/<book>.json, ".r1" for repaired specs
import json, os, re, sys, glob, collections
import pdfplumber
import pypdfium2 as pdfium
from spec_parse import run
from finder import page_scores, row_like
from score import align, norm, norm_set, FIELDS

D = "../data/"
FINISH_SHAPE = re.compile(r"^(?:6\d\d[A-Z]?|US\d{1,2}[A-Z]?|\d{2}[A-Z]{1,2}|BLK|BK|BLACK|AL|ALM|CLR|MIL|A|AA|DKB|GRY|SP\d+|PC|PRIME|PRIMED|\d{3}-\d{3})$", re.I)


def literal_prefix(regex):
    m = re.match(r"\^?((?:[A-Za-z #:]|\\[.#:])+)", regex)
    p = (m.group(1) if m else "").replace("\\", "").strip()
    return p if len(p) >= 2 else None


def page_texts(path):
    pdf = pdfium.PdfDocument(path)
    return [pdf[i].get_textpage().get_text_range().splitlines() for i in range(len(pdf))]


def expand_pages(spec, texts, runs, margin=3):
    # the compiled header regex is cheap to run over the whole book: pull in set pages the finder missed
    pages = {p for a, b in runs for p in range(a, b + 1)}
    if spec.get("mode") == "grid":
        return sorted(pages)
    hdr = re.compile(spec["set_header"])
    added = True
    while added:
        added = False
        for i, lines in enumerate(texts):
            if i in pages or not any(hdr.search(l.strip()) for l in lines):
                continue
            if any(abs(i - p) <= margin for p in pages):
                pages.add(i); added = True
                # the page before a header page may hold that set's components' tail; the next page its continuation
                for j in (i + 1,):
                    if j < len(texts) and any(row_like(l) for l in texts[j]):
                        pages.add(j)
    # fill small holes so a set never skips a page
    s = sorted(pages)
    for a, b in zip(s, s[1:]):
        if 1 < b - a <= 3:
            pages.update(range(a + 1, b))
    return sorted(pages)


def audit(spec, sets, texts, pages, scores):
    flags = []
    pset = set(pages)
    if spec.get("mode") != "grid":
        pre = literal_prefix(spec["set_header"])
        hdr = re.compile(spec["set_header"])
        if pre:
            miss = [(i, l.strip()) for i in pages for l in texts[i]
                    if l.strip().lower().startswith(pre.lower()) and not hdr.search(l.strip())]
            if miss:
                flags.append({"check": "header_near_miss", "count": len(miss), "examples": miss[:6]})
    comps_by_page = collections.Counter(c["page"] for s in sets for c in s["components"])
    orphan = [i for i in pages if scores[i] >= 3 and comps_by_page[i] == 0]
    if orphan:
        flags.append({"check": "pages_with_rows_but_no_components", "pages": orphan[:10], "count": len(orphan)})
    comps = [c for s in sets for c in s["components"]]
    if comps:
        long_codes = [c for c in comps if any(c.get(f) and len(re.sub(r"\(.*?\)", "", c[f]).split()) > 3 for f in ("finish", "mfr"))]
        if len(long_codes) > 0.1 * len(comps):
            flags.append({"check": "long_text_in_code_columns", "share": round(len(long_codes) / len(comps), 2),
                          "examples": [{k: c.get(k) for k in FIELDS} for c in long_codes[:3]]})
        fin = [c["finish"] for c in comps if c.get("finish")]
        mfr = [c["mfr"] for c in comps if c.get("mfr")]
        f_rate = sum(bool(FINISH_SHAPE.match(v)) for v in fin) / max(len(fin), 1)
        m_rate = sum(bool(FINISH_SHAPE.match(v)) for v in mfr) / max(len(mfr), 1)
        if mfr and m_rate > 0.5 and m_rate > f_rate:
            flags.append({"check": "mfr_column_looks_like_finish", "mfr_finish_shaped": round(m_rate, 2), "finish_finish_shaped": round(f_rate, 2)})
        expected = sum(scores[i] for i in pages)
        if expected and len(comps) < 0.6 * expected:
            flags.append({"check": "low_coverage", "components": len(comps), "row_like_lines": expected})
    empty = [s["set_number"] for s in sets if not s["components"] and not s.get("status")]
    if len(empty) > max(2, 0.15 * len(sets)):
        flags.append({"check": "many_empty_sets", "examples": empty[:8], "count": len(empty)})
    return flags


def score_book(name, sets):
    b = collections.Counter()
    for gt_file in sorted(glob.glob(f"eval/gt/{name}_p*.json")):
        page = int(re.search(r"_p(\d+)\.json$", gt_file).group(1))
        gt = json.load(open(gt_file))
        ours = [c for s in sets for c in s["components"] if c.get("page") == page]
        gt_all = [c for s in gt["sets"] for c in s["components"]]
        gt_sets = {norm_set(s["set_number"]) for s in gt["sets"] if s.get("starts_on_page", True)}
        our_sets = {norm_set(s["set_number"]) for s in sets if any(l["page"] == page for l in s["location"])}
        b["gt_sets"] += len(gt_sets); b["sets_found"] += len(gt_sets & our_sets)
        b["gt_comps"] += len(gt_all); b["our_comps"] += len(ours)
        for g, o in align(gt_all, ours):
            b["matched"] += 1
            for f in FIELDS:
                gv, ov = (g.get(f), o.get(f)) if f == "qty" else (norm(g.get(f)), norm(o.get(f)))
                b[f"ok_{f}"] += gv == ov
            if (norm(g.get("mfr")) and norm(o.get("finish")) == norm(g.get("mfr"))) or \
               (norm(g.get("finish")) and norm(o.get("mfr")) == norm(g.get("finish"))):
                b["swaps"] += 1
    return b


def main(suffix=""):
    plan = json.load(open("eval/e2e_plan.json"))
    os.makedirs("out_e2e", exist_ok=True)
    tot, rows = collections.Counter(), []
    for name, p in plan.items():
        spec_file = f"specs_e2e/{name}{suffix}.json"
        if not os.path.exists(spec_file):
            spec_file = f"specs_e2e/{name}.json"
        if not os.path.exists(spec_file):
            print(f"{name}: no spec"); continue
        spec = json.load(open(spec_file))
        path = D + p["file"]
        texts = page_texts(path)
        scores, _ = page_scores(path)
        pages = expand_pages(spec, texts, p["runs"])
        try:
            sets = run(spec, pdfplumber.open(path), pages)
        except Exception as e:
            print(f"{name}: crashed {e!r}"); continue
        flags = audit(spec, sets, texts, pages, scores)
        json.dump({"spec": spec_file, "pages": pages, "flags": flags, "sets": sets}, open(f"out_e2e/{name}{suffix}.json", "w"), indent=1)
        b = score_book(name, sets)
        b["n_sets"] = len(sets); b["n_comps"] = sum(len(s["components"]) for s in sets)
        tot.update(b)
        rows.append((name, b, [f["check"] for f in flags]))
    pct = lambda a, b: f"{100 * a / b:5.1f}" if b else "   - "
    print(f"{'book':10s} {'sets':>5s} {'comps':>5s}  gt_sets  rec  prec " + " ".join(f"{f[:6]:>6s}" for f in FIELDS) + " swaps  audit flags")
    for name, b, fl in rows + [("TOTAL", tot, [])]:
        print(f"{name:10s} {b['n_sets']:5d} {b['n_comps']:5d}  {b['sets_found']:>2}/{b['gt_sets']:<3} {pct(b['matched'], b['gt_comps'])} {pct(b['matched'], b['our_comps'])} "
              + " ".join(f"{pct(b['ok_' + f], b['matched']):>6s}" for f in FIELDS) + f"  {b['swaps']:3d}  {','.join(fl)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
