# compute caveat tags for every labeled page once and freeze them into eval/tags.json
# the scorer reads that file, so a changed spec cannot move components between tiers
# usage: python bench_tags.py [results dir]   rerun only when labels are added or edited
import json, re, sys, glob, hashlib
import pdfplumber
from lines import page_lines
from spec_parse import calibrate
from bench import result, plan

HARD = {"centered_cells", "grid_table", "embedded_mfr", "struck_page", "column_drift"}


def struck_words(page, lines):
    segs = [(o["x0"], o["x1"], (o["top"] + o["bottom"]) / 2) for o in page.lines + page.rects if o["bottom"] - o["top"] < 2.5 and o["x1"] - o["x0"] > 4]
    n = 0
    for l in lines:
        for w in l["words"]:
            mid = (w["top"] + w["bottom"]) / 2
            if any(s[0] <= w["x0"] + 1 and s[1] >= w["x1"] - 1 and abs(s[2] - mid) < 1.5 for s in segs):
                n += 1
    return n


def drift(spec, lines):
    if spec.get("mode") == "grid":
        return 0
    cal = {c["field"]: c["x"] for c in calibrate(spec, lines)["columns"]}
    return max((abs(cal[c["field"]] - c["x"]) for c in spec["columns"] if c["field"] in ("finish", "mfr")), default=0)


def misaligned(spec, lines, near=5):
    # columns moved too far to snap: most rows have no word starting at the spec's finish or mfr x
    if spec.get("mode") == "grid":
        return False
    row = re.compile(spec["row_start"])
    q = min(c["x"] for c in spec["columns"])
    rows = [l for l in lines if row.match(l["words"][0]["text"]) and abs(l["words"][0]["x0"] - q) < 15]
    if len(rows) < 3:
        return False
    for c in spec["columns"]:
        if c["field"] in ("finish", "mfr"):
            hit = sum(any(abs(w["x0"] - c["x"]) <= near + 4 for w in l["words"]) for l in rows)
            if hit < 0.5 * len(rows):
                return True
    return False


def source_line(gt_comp, lines):
    key = " ".join((gt_comp.get("description") or gt_comp.get("catalog") or "").split()[:2]).upper()
    if not key:
        return None
    return next((l for l in lines if key in l["text"].upper()), None)


def page_tags(book, page_no, spec, pdf):
    page = pdf.pages[page_no]
    lines = page_lines(page)
    tags = set()
    if struck_words(page, lines) >= 2:
        tags.add("struck_page")
    if drift(spec, lines) > 8 or misaligned(spec, lines):
        tags.add("column_drift")
    return tags, lines


def comp_tags(c, spec, lines):
    t = set()
    for f in ("mfr", "finish"):
        v = (c.get(f) or "").strip().upper()
        if v and re.fullmatch(r"[A-Z]{1,2}", v):
            t.add("ambiguous_code")
    if c.get("qty") is None:
        t.add("missing_qty")
    fields = set(spec["columns"].values()) if spec.get("mode") == "grid" else {x["field"] for x in spec["columns"]}
    if any(f in fields and not c.get(f) for f in ("finish", "mfr")):
        t.add("empty_code")
    if c.get("mfr") and re.search(r"[a-z]", c["mfr"]):
        t.add("full_name_mfr")
    src = source_line(c, lines)
    text = " ".join(filter(None, [c.get("description"), c.get("catalog")])).upper()
    if src is not None and any(tok not in src["text"].upper() for tok in text.split()):
        t.add("wrapped")
        if spec.get("valign") == "middle":
            t.add("centered_cells")
    if spec.get("mode") == "grid":
        t.add("grid_table")
        if spec.get("mfr_split"):
            t.add("embedded_mfr")
    return t


def tier(tags):
    if not tags:
        return "T0 trivial"
    if len(tags) == 1 and not tags & HARD:
        return "T1 one caveat"
    return "T2 hard"



def freeze(results_dir="out_e2e"):
    out = {"specs": {}, "pages": {}}
    pdfs = {}
    for gt_file in sorted(glob.glob("eval/gt/*.json")):
        book, page_no = re.match(r"eval/gt/(\w+)_p(\d+)\.json", gt_file).groups()
        page_no = int(page_no)
        if book not in plan:
            continue
        spec_path = result(results_dir, book)["spec"]
        spec_text = open(spec_path).read()
        spec = json.loads(spec_text)
        out["specs"][book] = {"path": spec_path, "sha1": hashlib.sha1(spec_text.encode()).hexdigest()[:12]}
        pdfs.setdefault(book, pdfplumber.open("../data/" + plan[book]["file"]))
        ptags, lines = page_tags(book, page_no, spec, pdfs[book])
        gt = json.load(open(gt_file))
        dense = len(gt["sets"]) >= 4
        page = {"page_tags": sorted(ptags), "seen_by_spec_writer": page_no in plan[book]["dump_pages"], "sets": []}
        for s in gt["sets"]:
            st = set(ptags)
            status = s.get("status", "active")
            if status in ("not_used", "moved"):
                st.add(status)
            if not s.get("starts_on_page", True) or s.get("continues_on_next_page"):
                st.add("multi_page")
            if dense:
                st.add("dense_page")
            comps = []
            for c in s["components"]:
                t = comp_tags(c, spec, lines) | st
                comps.append({"description": c.get("description"), "tags": sorted(t), "tier": tier(t - {"dense_page"})})
            page["sets"].append({"set_number": s["set_number"], "tags": sorted(st), "components": comps})
        out["pages"][f"{book}_p{page_no}"] = page
    json.dump(out, open("eval/tags.json", "w"), indent=1)
    n = sum(len(s["components"]) for p in out["pages"].values() for s in p["sets"])
    print(f"froze tags for {len(out['pages'])} pages, {n} components into eval/tags.json")


if __name__ == "__main__":
    freeze(*sys.argv[1:])
