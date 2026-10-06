# the viewer's api: books, results, page images, spec edits with a rerun, corrections, export
import glob, json, os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import pdfplumber
from hwsets.extract import extract_book, spec_name
from hwsets.spec import validate_spec

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
        r = extract_book(pdf_path(book_id), spec_dir=SPECS, allow_llm=bool(os.environ.get("ANTHROPIC_API_KEY")) or os.path.exists(os.path.join(ROOT, ".env")))
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
                    "has_spec": os.path.exists(os.path.join(SPECS, book_id + ".json"))})
    return out


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
