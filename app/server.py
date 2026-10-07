# the viewer's api: books, results, page images, spec edits with a rerun, corrections, export
import glob, json, os, re
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import pdfplumber
from hwsets.extract import extract_book, spec_name
from hwsets.spec import validate_spec, dump
from hwsets.finder import find_schedule
from hwsets.lines import page_lines
from hwsets import compile as compiler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, OUT, SPECS, CORR, CACHE = (os.path.join(ROOT, d) for d in ("data", "out", "specs", "corrections", "cache/pages"))
for d in (OUT, SPECS, CORR, CACHE):
    os.makedirs(d, exist_ok=True)
app = FastAPI()


# every pdf under data/, keyed the same way the specs are
#   {"village-of-oswego-specifications-volume-1": "/.../data/village-of-oswego/SPECIFICATIONS VOLUME 1.pdf", ...}
def books():
    return {spec_name(p): p for p in sorted(glob.glob(os.path.join(DATA, "**", "*.pdf"), recursive=True))}


def pdf_path(book_id):
    p = books().get(book_id)
    if not p:
        raise HTTPException(404, "no such book")
    return p


def key_available():
    return bool(os.environ.get("ANTHROPIC_API_KEY")) or os.path.exists(os.path.join(ROOT, ".env"))


def result_path(book_id):
    return os.path.join(OUT, book_id + ".json")


# overlay the saved corrections on a result: a correction names a set, a page, a row index and a field.
# one whose row no longer exists after a rerun is dropped and reported
#   {"set_number": "18", "page": 428, "row": 2, "field": "mfr", "value": "IVE"}
def apply_corrections(result, corrections):
    dropped = []
    for c in corrections:
        rows = [comp for s in result["sets"] if s["set_number"] == c["set_number"]
                for comp in s["components"] if comp["page"] == c["page"]]
        if c["row"] < len(rows):
            rows[c["row"]][c["field"]] = c["value"]
            rows[c["row"]].setdefault("corrected", []).append(c["field"])
        else:
            dropped.append(c)
    result["corrections_dropped"] = dropped
    return result


def corrections_for(book_id):
    p = os.path.join(CORR, book_id + ".json")
    return json.load(open(p)) if os.path.exists(p) else []


# run the extractor for a book and save the result. no api call unless the key is set and no spec exists
def rerun(book_id):
    try:
        r = extract_book(pdf_path(book_id), spec_dir=SPECS, allow_llm=key_available())
    except SystemExit as e:
        raise HTTPException(409, str(e))
    r["id"] = book_id
    r = apply_corrections(r, corrections_for(book_id))
    json.dump(r, open(result_path(book_id), "w"), indent=1)
    return r


@app.get("/api/books")
def list_books():
    out = []
    for book_id, p in books().items():
        r = json.load(open(result_path(book_id))) if os.path.exists(result_path(book_id)) else None
        out.append({"id": book_id, "file": os.path.basename(p), "project": os.path.basename(os.path.dirname(p)),
                    "status": r["status"] if r else "not run", "sets": len(r["sets"]) if r else None,
                    "has_spec": os.path.exists(os.path.join(SPECS, book_id + ".json")), "key": key_available()})
    return out


# a dropped pdf lands under data/uploads/ and is listed like any other book. extraction happens on first open
@app.post("/api/books/upload")
async def upload(file: UploadFile):
    name = re.sub(r"[^\w. -]+", "_", os.path.basename(file.filename or "upload.pdf"))
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "only PDF files")
    path = os.path.join(DATA, "uploads", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(await file.read())
    return {"id": spec_name(path), "file": name}


@app.get("/api/books/{book_id}")
def get_book(book_id: str):
    if os.path.exists(result_path(book_id)):
        return json.load(open(result_path(book_id)))
    return rerun(book_id)


@app.get("/api/books/{book_id}/spec")
def get_spec(book_id: str):
    p = os.path.join(SPECS, book_id + ".json")
    if not os.path.exists(p):
        raise HTTPException(404, "no spec yet")
    return json.load(open(p))


# page n, 1-based, as a png at 110 dpi, rendered once and kept
@app.get("/api/books/{book_id}/pages/{n}.png")
def page_png(book_id: str, n: int):
    png = os.path.join(CACHE, f"{book_id}_{n}.png")
    if not os.path.exists(png):
        pdf = pdfplumber.open(pdf_path(book_id))
        if not 1 <= n <= len(pdf.pages):
            raise HTTPException(404, "no such page")
        pdf.pages[n - 1].to_image(resolution=110).save(png)
    return FileResponse(png)


# save an edited spec and rerun the whole book with it, no api call
@app.put("/api/books/{book_id}/spec")
def put_spec(book_id: str, spec: dict):
    try:
        validate_spec(spec)
    except Exception as e:
        raise HTTPException(400, f"bad spec: {e}")
    json.dump(spec, open(os.path.join(SPECS, book_id + ".json"), "w"), indent=1)
    return rerun(book_id)


def spec_path(book_id):
    return os.path.join(SPECS, book_id + ".json")


# the spec's differences in plain words, for the reviewer after a fix
#   -> ["set header pattern widened", "finish column moved from 462 to 470", "2 lines added to skip"]
def describe_changes(old, new):
    out = []
    if old.get("set_header") != new.get("set_header"):
        out.append("set header pattern changed")
    if len(new.get("set_header_extra", [])) != len(old.get("set_header_extra", [])):
        out.append("a set header spelling added")
    if old.get("row_start") != new.get("row_start"):
        out.append("row start pattern changed")
    oc = {c["field"]: c["x"] for c in old.get("columns", [])} if isinstance(old.get("columns"), list) else {}
    nc = {c["field"]: c["x"] for c in new.get("columns", [])} if isinstance(new.get("columns"), list) else {}
    for f in nc:
        if f not in oc:
            out.append(f"{f} column added at x={nc[f]}")
        elif oc[f] != nc[f]:
            out.append(f"{f} column moved from {oc[f]} to {nc[f]}")
    for f in oc:
        if f not in nc:
            out.append(f"{f} column removed")
    for key, label in (("skip", "skipped line patterns"), ("end", "end patterns")):
        d = len(new.get(key, [])) - len(old.get(key, []))
        if d:
            out.append(f"{abs(d)} {label} {'added' if d > 0 else 'removed'}")
    for key in ("set_meta", "note_line", "valign"):
        if old.get(key) != new.get(key):
            out.append(f"{key.replace('_', ' ')} changed")
    return out or ["nothing changed"]


# the column guides: new x per field, every set in the book reruns, no model call
@app.put("/api/books/{book_id}/columns")
def put_columns(book_id: str, body: dict):
    spec = json.load(open(spec_path(book_id)))
    if spec.get("mode") == "grid":
        raise HTTPException(400, "this book is a ruled table, its columns come from the printed headings")
    xs = {c["field"]: float(c["x"]) for c in body.get("columns", [])}
    new = dict(spec, columns=[{**c, "x": xs.get(c["field"], c["x"])} for c in spec["columns"]])
    validate_spec(new)
    json.dump(new, open(spec_path(book_id), "w"), indent=1)
    r = rerun(book_id)
    r["changes"] = describe_changes(spec, new)
    return r


# the lines of a page with their boxes, so the viewer can make them clickable
@app.get("/api/books/{book_id}/pages/{n}/lines")
def lines_of(book_id: str, n: int):
    pdf = pdfplumber.open(pdf_path(book_id))
    if not 1 <= n <= len(pdf.pages):
        raise HTTPException(404, "no such page")
    return [{"text": l["text"], "bbox": [round(l["x0"], 1), round(l["top"], 1), round(l["x1"], 1), round(l["bottom"], 1)]}
            for l in page_lines(pdf.pages[n - 1])]


# a line's text as a pattern that matches that line and its siblings: digits become \d+, spaces \s+
#   "DOOR HARDWARE 087100 - 7" -> "^\s*DOOR\s+HARDWARE\s+\d+\s+\-\s+\d+\s*$"
def line_pattern(text):
    body = r"\s+".join(re.sub(r"\d+", "DIGITS", re.escape(w)).replace("DIGITS", r"\d+") for w in text.split())
    return r"^\s*" + body + r"\s*$"


# a header pattern from a clicked line: the words before the set number literally, then the number as num
#   "Hardware Set/Group #01" -> "^\s*Hardware\s+Set/Group\s*#?\s*(?P<num>[A-Za-z0-9][\w.\-/]*)(?:\s+(?P<desc>.*))?$"
def header_pattern(text):
    words = text.split()
    i = next((k for k, w in enumerate(words) if re.search(r"\d", w)), len(words) - 1)
    prefix = r"\s+".join(re.escape(w) for w in words[:i]) if i else ""
    return r"^\s*" + prefix + r"\s*(?:#|No\.?|:)?\s*(?P<num>[A-Za-z0-9][\w.\-/]*)(?:\s+(?P<desc>.*))?$"


# what a reviewer says a clicked line is: header, skip, note or meta. the spec gets a literal rule, the book reruns
@app.post("/api/books/{book_id}/lines")
def tag_line(book_id: str, body: dict):
    spec = json.load(open(spec_path(book_id)))
    if spec.get("mode") == "grid":
        raise HTTPException(400, "this book is a ruled table, lines cannot be tagged")
    text, kind = (body.get("text") or "").strip(), body.get("kind")
    if not text or kind not in ("header", "skip", "note", "meta"):
        raise HTTPException(400, "need a line and a kind")
    new = json.loads(json.dumps(spec))
    if kind == "header":
        new.setdefault("set_header_extra", []).append(header_pattern(text))
    elif kind == "skip":
        new.setdefault("skip", []).append(line_pattern(text))
    else:
        key = "note_line" if kind == "note" else "set_meta"
        pat = r"^\s*" + re.escape(" ".join(text.split()[:2]))
        new[key] = f"(?:{new[key]})|(?:{pat})" if new.get(key) else pat
    validate_spec(new)
    json.dump(new, open(spec_path(book_id), "w"), indent=1)
    r = rerun(book_id)
    r["changes"] = {"header": ["a set header spelling added"], "skip": ["a line pattern added to skip"],
                    "note": ["a note pattern added"], "meta": ["a header block pattern added"]}[kind]
    return r


# a reviewer's note in plain words goes to the repair call with the page they were looking at
@app.post("/api/books/{book_id}/feedback")
def feedback(book_id: str, body: dict):
    if not key_available():
        raise HTTPException(409, "this needs the API key")
    spec = json.load(open(spec_path(book_id)))
    path = pdf_path(book_id)
    texts, scores, runs = find_schedule(path)
    page = int(body.get("page") or 0)
    lines = [l.strip() for l in texts[page - 1] if l.strip()][:40] if 0 < page <= len(texts) else []
    result = json.load(open(result_path(book_id)))
    flags = result.get("flags", []) + [{"check": "reviewer", "count": 1,
                                         "examples": [{"note": body.get("note", ""), "page": page, "lines": lines}]}]
    text = dump(pdfplumber.open(path), compiler.pick_samples(runs, scores))
    try:
        new = compiler.repair(spec, flags, text)
    except Exception as e:
        raise HTTPException(500, f"the model call failed: {e}")
    json.dump(new, open(spec_path(book_id), "w"), indent=1)
    r = rerun(book_id)
    r["changes"] = describe_changes(spec, new)
    return r


@app.post("/api/books/{book_id}/corrections")
def post_correction(book_id: str, c: dict):
    cs = corrections_for(book_id) + [c]
    json.dump(cs, open(os.path.join(CORR, book_id + ".json"), "w"), indent=1)
    r = json.load(open(result_path(book_id)))
    r = apply_corrections(r, cs)
    json.dump(r, open(result_path(book_id), "w"), indent=1)
    return r


@app.get("/api/books/{book_id}/export")
def export(book_id: str):
    if not os.path.exists(result_path(book_id)):
        raise HTTPException(404, "not run yet")
    return FileResponse(result_path(book_id), filename=book_id + ".json", media_type="application/json")


app.mount("/", StaticFiles(directory=os.path.join(ROOT, "app", "static"), html=True), name="static")
