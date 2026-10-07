# Hardware sets: frontend implementation

Companion to [IMPLEMENTATION_BACKEND.md](IMPLEMENTATION_BACKEND.md). The viewer reads the `BookResult` the backend writes and calls back into it for reruns. Built: `uv run hwsets serve`, then http://localhost:8000. The look copies the Hardware step of the demo on fresco.build: Inter, white cards on a pale green page, green boxes on the page image.

## 1. Goals

- Open a book, see a page with one box per set and the extracted components beside it. Click a component, see its box.
- Edit the spec in place and rerun the book with no LLM call. One edit fixes every set in the book.
- Correct a wrong value in the table (bonus: feedback UI). Corrections survive a spec rerun.
- Show the audit flags and the per-field confidence (bonus) so a reviewer knows where to look.
- No build step. `uv run hwsets serve` and a browser.

## 2. Stack

FastAPI serving a JSON API and one static page, vanilla JS, no framework. Pages are rendered to PNG on the server by pdfplumber and cached, and bboxes are scaled client side from the page size in the result. Reason: a reviewer runs one command, and the whole UI is three files.

## 3. Screens

**Library.** A drop zone for a new spec PDF (`POST /api/books/upload`, saved under `data/uploads/`, extracted on first open), then a searchable table of the PDFs under `data/`, ten per page with prev and next arrows: project, file, status chip (`extracted`, `needs review`, `no sets`, `not run yet`) and set count. Click a row to open. "All books" in the top bar comes back here.

**Book view**, one screen, two panes side by side, the page on the left with about half the width and a drag handle, the components on the right. The set list is a dropdown in the components pane's header, doors and notes a strip under it, the spec editor folds out below both:

| Pane | Shows | Actions |
| :--- | :--- | :--- |
| Page | Page image with a box per set, the selected set's boxes in a stronger color, a component's box when clicked | Previous and next page, jump to a set's first page |
| Sets | Set number, description, status, page range, flag count | Click selects the set and jumps the page |
| Components | Table of qty, description, catalog, finish, mfr, notes for the selected set, low-confidence cells tinted | Click a cell to edit it (correction), click the row to highlight its box |
| Fix it | A plain-words box ("the set on this page is missing", "finish and maker are swapped"), and Adjust columns on the page pane, which draws the spec's columns as draggable lines over the page image. | The note goes to the repair call with the page's lines, the model edits the spec, the book reruns, and the reply says what changed in plain words. Dragging the lines and applying sets the column x values and reruns with no model call |

## 4. Function trace

### Server

```
uv run hwsets serve                                                                   cli.py
├─ GET  /                                   static/index.html                         app/server.py
├─ GET  /api/books                          every PDF under data/, status, set count  app/server.py
├─ GET  /api/books/{id}                     cached BookResult, extract first if none  app/server.py
├─ GET  /api/books/{id}/pages/{n}.png       page to PNG at 110 dpi, cached            app/server.py
├─ PUT  /api/books/{id}/spec (kept for scripts, no UI)                save the edited spec, rerun, no LLM call  app/server.py
│  ├─ validate_spec(raw)                    schema check, compile the regexes         hwsets/spec.py
│  ├─ interpret(spec, pdf, pages)           every set again, 12 s for SAT             hwsets/spec.py
│  ├─ audit(...)                            fresh flags for the new spec              hwsets/audit.py
│  ├─ apply_corrections(sets, corrections)  overlay corrections/<id>.json             app/server.py
│  └─ to_result(...)                        rewrite out/<id>.json, return it          hwsets/extract.py
├─ POST /api/books/{id}/corrections         append one Correction, same rerun         app/server.py
└─ GET  /api/books/{id}/export              the BookResult as a download              app/server.py
```

### Client

```
app.js
├─ loadBooks()                   fill the book list
├─ openBook(id)                  fetch the result, draw the first set's page
│  ├─ drawPage(n)                image plus boxes, scaled by page_size
│  ├─ renderSets()               number, description, status, pages, flags
│  └─ renderComponents(set)      table, low-confidence cells tinted
├─ selectSet(set)                jump to its first page, highlight boxes
├─ selectComponent(c)            highlight one box
├─ saveSpec()                    PUT the text area, then openBook again
├─ correctCell(c, field, value)  POST a Correction, then openBook again
└─ exportJson()                  link to /export
```

## 5. Data

### Client state

```js
state = {
  book: BookResult | null,
  page: number,            // 1-based, as in the result
  set: HardwareSet | null,
  component: Component | null,
  spec: string,            // text area contents, may differ from book.spec until saved
}
```

### Correction

Written by `correctCell`, stored in `corrections/<id>.json`, read by `apply_corrections`.

```python
class Correction(TypedDict):
    set_number: str
    page: int
    # index of the row within the set on that page
    row: int
    # qty | description | catalog_number | finish | mfr | notes
    field: str
    value: str | int | None
```

Example: `{"set_number": "18", "page": 427, "row": 2, "field": "mfr", "value": "IVE"}`

### What the page draws

- Set box: `location[i].bbox` for the location whose `page` is the current page.
- Component box: `component.bbox`, on `component.page`.
- Both in PDF points with origin top left. Scale is `image_width / page_size[0]`.

## 6. Files

| File | Job |
| :--- | :--- |
| `app/server.py` | FastAPI routes, rerun, corrections, page cache |
| `app/static/index.html` | the one page |
| `app/static/app.js` | state, fetches, drawing |
| `app/static/style.css` | four-pane layout |
| `out/<id>.json` | current `BookResult` per book |
| `corrections/<id>.json` | corrections per book |
| `cache/pages/<id>_<n>.png` | rendered pages |

## 7. Build order

1. Read-only viewer: book list, page image, set boxes, components table. Done.
2. Spec editor with save and rerun. Built, then removed: a reviewer never sees a regex. The spec is edited only through the column guides, tagged lines and the Fix it box, or by hand in `specs/`.
3. Audit flags above the panes, a CONF column per row (its weakest filled cell, green from 0.9, amber from 0.8, red below) plus the amber tint on the cell itself and a "N cells to check" count in the set header, full names from the book's legend under maker and finish codes. Done.
4. Corrections, double-click a cell. Done.
6. Feedback without regex: the Fix it box (one model call), draggable column guides, and Tag a line: click any line on the page and say "this starts a set", "not a component, skip it", "this is a note" or "door numbers or header block". The server turns the clicked text into a literal rule (digits generalized) in `set_header_extra`, `skip`, `note_line` or `set_meta`, so it cannot break anything else, and the book reruns with no model call. Done. Tested on Star: "the set headed Hardware Set/Group #01 on this page is missing" widened the header pattern and the set appeared, whole-book set numbers found went from 1,172 to 1,174 of 1,175.
5. Export. Done.
