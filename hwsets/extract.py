# the pipeline for one PDF: find the schedule pages, get a spec, interpret, audit, repair once, write the result
import json, os, re
import pdfplumber
from .finder import find_schedule, widen_with_headers
from .spec import interpret, validate_spec
from .audit import audit
from . import compile as compiler


def spec_name(pdf_path):
    # the checked-in spec for a sample book is named after its folder and file
    #   "data/village-of-oswego/SPECIFICATIONS VOLUME 1.pdf" -> "village-of-oswego-specifications-volume-1"
    parent = os.path.basename(os.path.dirname(os.path.abspath(pdf_path)))
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    return re.sub(r"[^a-z0-9]+", "-", f"{parent} {stem}".lower()).strip("-")


def extract_book(pdf_path, spec_path=None, spec_dir="specs", allow_llm=True):
    # -> BookResult (see to_result). spec_path overrides the lookup in spec_dir
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


def to_result(pdf_path, pdf, status, spec_path, flags, sets):
    # the output file: 1-based pages, catalog -> catalog_number, every set and component with a status
    #   {"file": "SPECIFICATIONS VOLUME 1.pdf", "status": "extracted", "page_count": 584, "page_size": [612.0, 792.0],
    #    "spec": "specs/village-of-oswego-specifications-volume-1.json", "flags": [],
    #    "sets": [{"set_number": "18", "description": null, "status": "active", "moved_to": null,
    #              "doors": ["E120A E121B"], "notes": [],
    #              "location": [{"page": 428, "bbox": [72.0, 73.5, 530.2, 630.5]}],
    #              "components": [{"qty": 6, "description": "HINGE", "catalog_number": "5BB1HW 4.5 X 4.5 - NRP",
    #                              "mfr": "IVE", "finish": "652", "notes": null,
    #                              "page": 428, "bbox": [80.1, 98.2, 528.0, 121.7]}]}]}
    out_sets = []
    for s in sets:
        comps = [{"qty": c.get("qty"), "description": c.get("description"), "catalog_number": c.get("catalog"),
                  "mfr": c.get("mfr"), "finish": c.get("finish"), "notes": c.get("notes"),
                  "page": c["page"] + 1, "bbox": c["bbox"]} for c in s["components"]]
        out_sets.append({"set_number": s["set_number"], "description": s.get("description"),
                         "status": s.get("status", "active"), "moved_to": s.get("moved_to"),
                         "doors": s.get("meta", []), "notes": s.get("notes", []),
                         "location": [{"page": l["page"] + 1, "bbox": l["bbox"]} for l in s["location"]],
                         "components": comps})
    first = pdf.pages[0]
    return {"file": os.path.basename(pdf_path), "status": status, "page_count": len(pdf.pages),
            "page_size": [float(first.width), float(first.height)], "spec": spec_path, "flags": flags, "sets": out_sets}
