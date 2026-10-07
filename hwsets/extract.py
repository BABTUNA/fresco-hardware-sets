# the pipeline for one PDF: find the schedule pages, get a spec, interpret, audit, repair once, write the result
import json, os, re
import pdfplumber
from .finder import find_schedule, widen_with_headers
from .spec import interpret, validate_spec
from .audit import audit
from . import compile as compiler


# the checked-in spec for a sample book is named after its folder and file
#   "data/village-of-oswego/SPECIFICATIONS VOLUME 1.pdf" -> "village-of-oswego-specifications-volume-1"
def spec_name(pdf_path):
    parent = os.path.basename(os.path.dirname(os.path.abspath(pdf_path)))
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    return re.sub(r"[^a-z0-9]+", "-", f"{parent} {stem}".lower()).strip("-")


# -> BookResult (see to_result). spec_path overrides the lookup in spec_dir
def extract_book(pdf_path, spec_path=None, spec_dir="specs", allow_llm=True):
    texts, scores, runs = find_schedule(pdf_path)
    pdf = pdfplumber.open(pdf_path)

    if not runs:
        return to_result(pdf_path, pdf, "no_hardware_sets", None, [], [])
    spec_path = spec_path or os.path.join(spec_dir, spec_name(pdf_path) + ".json")
    text = None

    if os.path.exists(spec_path):
        spec = validate_spec(json.load(open(spec_path)))

    elif allow_llm:
        spec, text = compiler.compile_spec(pdf, runs, scores)
        os.makedirs(os.path.dirname(spec_path) or ".", exist_ok=True)
        json.dump(spec, open(spec_path, "w"), indent=1)

    else:
        raise SystemExit(f"no spec at {spec_path} and LLM calls are off")
    
    # using the spec made by the model, widen the runs to include any header pages, then interpret and audit
    pages = widen_with_headers(spec, texts, runs)
    sets = interpret(spec, pdf, pages)
    flags = audit(spec, sets, texts, pages, scores, pdf)
    
    if flags and allow_llm:
        # one repair round, then the book is marked for review if flags remain
        if text is None:
            text = compiler.dump(pdf, compiler.pick_samples(runs, scores))
        spec = compiler.repair(spec, flags, text)
        json.dump(spec, open(spec_path, "w"), indent=1)
        pages = widen_with_headers(spec, texts, runs)
        sets = interpret(spec, pdf, pages)
        flags = audit(spec, sets, texts, pages, scores, pdf)
    status = "needs_review" if flags else "extracted"
    return to_result(pdf_path, pdf, status, spec_path, flags, sets)


# the output file: 1-based pages, catalog -> catalog_number, every set and component with a status
#   {"file": "SPECIFICATIONS VOLUME 1.pdf", "status": "extracted", "page_count": 584, "page_size": [612.0, 792.0],
#    "spec": "specs/village-of-oswego-specifications-volume-1.json", "flags": [],
#    "sets": [{"set_number": "18", "description": null, "status": "active", "moved_to": null,
#              "doors": ["E120A E121B"], "notes": [],
#              "location": [{"page": 428, "bbox": [72.0, 73.5, 530.2, 630.5]}],
#              "components": [{"qty": 6, "description": "HINGE", "catalog_number": "5BB1HW 4.5 X 4.5 - NRP",
#                              "mfr": "IVE", "finish": "652", "notes": null,
#                              "page": 428, "bbox": [80.1, 98.2, 528.0, 121.7]}]}]}
# a per-field confidence from evidence already in hand: does the value look like its column (a finish code,
# a maker code, a catalog number with a digit), was the column snapped to this page's edges, did the row have a
# quantity, did it span several lines, and did the book pass the audit. 1.0 means nothing argued against it
#   in:  {"qty": 6, "description": "HINGE", "catalog": "5BB1HW 4.5 X 4.5", "finish": "652", "mfr": "IVE",
#         "_evidence": {"lines": 1, "qty_row": True, "calibrated": True, "snapped": ["catalog", "finish", "mfr"]}}, no flags
#   out: {"qty": 1.0, "description": 1.0, "catalog_number": 1.0, "finish": 1.0, "mfr": 1.0, "notes": 0.8}
# under 0.8 is worth a look. the viewer tints those cells
SHAPES = {
    # a finish is a short code: 652, 626/626, US26D, C26D, BSP, 613 (OIL RUBBED BRONZE)
    "finish": re.compile(r"^(?:\d{3}[A-Z]?(?:\s*\(.*\))?|US\d{1,2}[A-Z]?|C\d{2}[A-Z]?|\d{2}[A-Z]{1,2}|[A-Z]{1,5}|SP\d+|\d{3}(?:\s*/\s*\d{3})+|\d{3}-\d{3}|BY [A-Z ]+)$", re.I),
    # a maker is letters: IVE, McKinney, VON DUPRIN, PEMKO / NGP / ZERO, B/O
    "mfr": re.compile(r"^(?:[A-Za-z][A-Za-z.&'/ -]{0,28}\d?|B/O|TBD)$"),
    # a catalog cell is anything but a column heading
    "catalog": re.compile(r"^(?!(?:CATALOG(?: NUMBER| ?#)?|MODEL(?: NUMBER)?|PRODUCT)$).+", re.I),
    "description": re.compile(r"^(?!(?:DESCRIPTION|ITEM|QTY)$).*[A-Za-z]{3}", re.I),
}


def confidence(c, fields, flagged):
    ev = c.get("_evidence", {})
    out = {}
    for f in ("qty", "description", "catalog", "finish", "mfr", "notes"):
        if f not in fields and f != "notes":
            out[f] = None
            continue
        v = c.get(f)
        if v is None:
            # the column exists and nothing was read into it: neutral, not suspicious
            out[f] = 0.8 if f in fields else None
            continue
        score = 0.95 if ev.get("grid") else 1.0
        if f in SHAPES and not SHAPES[f].search(str(v)):
            score *= 0.6
        if f in ("catalog", "finish", "mfr", "notes") and not ev.get("grid"):
            # a code column that did not snap to an edge on this page sits where the spec guessed
            if not ev.get("calibrated"):
                score *= 0.9
            elif f not in ev.get("snapped", []):
                score *= 0.85
        if f in ("description", "catalog") and ev.get("lines", 1) > 1:
            score *= 0.9
        if ev.get("qty_row") is False:
            score *= 0.8
        if flagged:
            score *= 0.8
        out[f] = round(score, 2)
    out["catalog_number"] = out.pop("catalog")
    return out


def to_result(pdf_path, pdf, status, spec_path, flags, sets):
    spec = json.load(open(spec_path)) if spec_path and os.path.exists(spec_path) else {}
    fields = set(spec.get("columns", {}).values()) if spec.get("mode") == "grid" else {c["field"] for c in spec.get("columns", [])}
    if spec.get("mode") == "grid":
        fields |= {"catalog", "mfr"} if "product" in fields else set()
    out_sets = []
    for s in sets:
        comps = [{"qty": c.get("qty"), "description": c.get("description"), "catalog_number": c.get("catalog"),
                  "mfr": c.get("mfr"), "finish": c.get("finish"), "notes": c.get("notes"),
                  "page": c["page"] + 1, "bbox": c["bbox"], "confidence": confidence(c, fields, bool(flags))} for c in s["components"]]
        out_sets.append({"set_number": s["set_number"], "description": s.get("description"),
                         "status": s.get("status", "active"), "moved_to": s.get("moved_to"),
                         "doors": s.get("meta", []), "notes": s.get("notes", []),
                         "location": [{"page": l["page"] + 1, "bbox": l["bbox"]} for l in s["location"]],
                         "components": comps})
    first = pdf.pages[0]
    return {"file": os.path.basename(pdf_path), "status": status, "page_count": len(pdf.pages),
            "page_size": [float(first.width), float(first.height)], "spec": spec_path, "flags": flags, "sets": out_sets}
