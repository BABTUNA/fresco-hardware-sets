# Hardware sets: backend implementation

Companion to [PLAN.md](PLAN.md). The viewer is in [IMPLEMENTATION_FRONTEND.md](IMPLEMENTATION_FRONTEND.md). Function and file names here are the target names for `hwsets/`. The same logic already runs in `experiments/` under older names, listed in the files table.

## 1. Goals

**Find** (`finder.py`)
- Locate every hardware schedule in a book without knowing its header wording.
- All 20 sample schedules found, zero page runs on the 21 PDFs that have no sets.
- SAT TDP (3,930 pages) scanned in under 10 seconds.

**Compile** (`compile.py`)
- One Claude call per book turns 2 sample pages into a layout spec.
- At most one repair call, and only when the audit flags something.
- Compiled specs saved to `specs/`, so a rerun or a reviewer needs no API key.

**Interpret** (`spec.py`, `lines.py`)
- Deterministic. Same spec and PDF give the same output every time.
- Every extracted value comes from real words on the page, with a page number and bbox.
- Handles wrapped rows, vertically centered cells, missing qty (null, never guessed), sets across page breaks, NOT USED and "moved to" sets, ruled grid tables, column drift between pages, struck-through revisions.
- Manufacturer vs finish decided by column for the whole book, never by the value alone.

**Audit** (`audit.py`)
- Flag every book whose spec misses or merges sets.
- Raise no flags on books that extracted cleanly.

**Output** (`extract.py`)
- Every set has `set_number`, `description`, `location`, `components[]` with `qty`, `description`, `catalog_number`, `mfr`, `finish`, `notes`.
- Book status is `extracted`, `no_hardware_sets` or `needs_review`. Set status is `active`, `not_used` or `moved`.
- Per-field confidence (bonus).

**Eval** (`eval/bench.py`)
- One command prints exact rows, sets fully correct, precision and mfr/finish swaps, in total, by difficulty tier, by caveat and by book.
- Current bar: 98.4% of 2,218 rows exact, 94.5% of 311 sets fully correct, 0 swaps. Held out: 97.2% of rows, 89.5% of sets.

**Code size**
- `hwsets/` stays under about 800 lines.

## 2. Function trace

### Extract a book

```
hwsets extract book.pdf -o out.json                                                                                                cli.py
└─ extract_book(pdf_path, spec_dir)                              whole pipeline for one PDF                                        extract.py
   ├─ find_schedule(pdf_path) -> texts, scores, runs             which pages hold sets                                             finder.py
   │  ├─ page_texts(pdf_path)                                    raw text per page, pypdfium2, fast                                finder.py
   │  ├─ row_like(text_line)                                     qty, words, short codes at the end?                               finder.py
   │  └─ group_runs(scores, vocab)                               pages with 2+ rows into runs, drop other trades' lists            finder.py
   ├─ if no runs: return BookResult(status="no_hardware_sets")                                                                     extract.py
   ├─ load_or_compile(pdf_path, runs, scores, spec_dir) -> Spec  specs/<book>.json if it exists, else compile                      compile.py
   │  ├─ pick_samples(runs, scores)                              the 2 densest schedule pages                                      compile.py
   │  ├─ dump(pdf, pages)                                        text with each run tagged by its x, all the model sees            compile.py
   │  │  └─ page_lines(page)                                     pdfplumber words into lines with coordinates                      lines.py
   │  ├─ ask_claude(SPEC_PROMPT, dump)                           one API call, returns the spec JSON                               compile.py
   │  └─ validate_spec(raw)                                      schema check, compile the regexes, fail loudly                    spec.py
   ├─ widen_with_headers(spec, texts, runs) -> pages             add header pages near the runs the finder missed                  finder.py
   ├─ interpret(spec, pdf, pages) -> list[HardwareSet]           columns or grid mode by the spec                                  spec.py
   │  ├─ run_columns(spec, pdf, pages)                           walk pages, start a set at each header                            spec.py
   │  │  ├─ page_lines(page)                                                                                                       lines.py
   │  │  │  └─ mark_struck(words, page)                          thin rule through mid-height marks a word struck                  lines.py
   │  │  ├─ calibrate(spec, lines)                               re-snap column x to this page's aligned edges                     spec.py
   │  │  ├─ classify(line, layout)                               header, meta, note, anchor or other                               spec.py
   │  │  ├─ resolve_top(layout, items)                           wrapped lines sit below their row                                 spec.py
   │  │  ├─ resolve_middle(layout, items)                        wrapped lines sit above and below                                 spec.py
   │  │  │  └─ assemble(layout, anchor, extra) -> Component      one row from its lines, fields by x, bbox                         spec.py
   │  │  │     ├─ Layout.assign(words)                           word to field by x, text runs cannot jump columns                 spec.py
   │  │  │     └─ parse_qty(text)                                3, 3.0 -> 3, blank, __, As Req -> null                            spec.py
   │  │  └─ set_status(hardware_set)                             active, not_used, or moved with moved_to                          spec.py
   │  └─ run_grid(spec, pdf, pages)                              ruled tables, header row maps labels to fields                    spec.py
   │     └─ split_mfr(product, sep)                              "IVES - 5BB1" -> mfr IVES, catalog 5BB1                           spec.py
   ├─ audit(spec, sets, texts, pages, scores) -> list[Flag]      does the result fit the book?                                     audit.py
   │  ├─ header_near_miss                                        lines that start like the header but did not match                audit.py
   │  ├─ rows_without_components                                 pages with rows and nothing extracted                             audit.py
   │  ├─ long_text_in_code_columns                               4+ words in finish or mfr, a column x is wrong                    audit.py
   │  ├─ mfr_looks_like_finish                                   mfr column full of 626, US26D: columns swapped                    audit.py
   │  ├─ low_coverage                                            far fewer components than row-like lines                          audit.py
   │  └─ suspicious_qty                                          qty over 99 with no catalog                                       audit.py
   ├─ if flags: repair(spec, flags, dump) -> Spec                one more call with the flags, then interpret + audit again, once  compile.py
   ├─ read_legends(pdf, pages) -> Legend                         code/name lists printed in the book, bonus                        legend.py
   ├─ confidence(component, layout, flags)                       per-field score from column snap, value shape, audit, bonus       extract.py
   └─ to_result(sets, flags, pdf, spec) -> BookResult            output schema, 1-based pages, book status                         extract.py
```

### Files

| File | Job | Ported from |
| :--- | :--- | :--- |
| `hwsets/lines.py` | words to lines, watermark and icon filtering, strike marks | `experiments/lines.py` |
| `hwsets/finder.py` | page scoring, runs, header widening | `experiments/finder.py`, `expand_pages` in `experiments/e2e.py` |
| `hwsets/spec.py` | spec schema, `Layout`, columns and grid interpreters | `experiments/spec_parse.py` |
| `hwsets/compile.py` | sample pages, dump, Claude compile and repair calls | `dump` in `experiments/spec_parse.py`, `experiments/SPEC_PROMPT.md` |
| `hwsets/audit.py` | audit checks | `audit` in `experiments/e2e.py` |
| `hwsets/legend.py` | legend parsing (bonus) | new |
| `hwsets/extract.py` | pipeline, confidence, output schema | `main` in `experiments/e2e.py` |
| `hwsets/cli.py` | `extract`, `serve` commands | new |
| `hwsets/prompts/spec.md` | spec compile prompt | `experiments/SPEC_PROMPT.md` |
| `hwsets/prompts/repair.md` | repair prompt | repair subagent prompt |
| `specs/<book>.json` | compiled spec per sample book | `experiments/specs_e2e/` |
| `eval/books.json` | book id to PDF path | `experiments/eval/e2e_plan.json` |
| `eval/gt/<book>_p<page>.json` | labeled pages | `experiments/eval/gt/` |
| `eval/score.py` | scorer | `experiments/score.py` |
| `scripts/download_data.sh` | fetch the 43 PDFs | exists |

## 3. Data structures

Coordinates are PDF points with the origin at the top left of the page. Page numbers are 0-based inside the pipeline and 1-based in the output.

### Word and Line

Made by `page_lines`. Used by `calibrate`, `classify`, `resolve_*`, `assemble`, `dump`.

```python
class Word(TypedDict):
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    # set by mark_struck
    struck: bool

class Line(TypedDict):
    # words sorted left to right
    words: list[Word]
    # words joined with single spaces
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    # 0-based page index, set when a line is tagged
    page: int
```

Example: `{"text": "6 EA HINGE 5BB1HW 4.5 X 4.5 - NRP AT 652 IVE", "x0": 80.1, "top": 98.2, ...}`

### Runs

Made by `group_runs`. Used by `load_or_compile`, `widen_with_headers`.

```python
# inclusive 0-based page ranges, e.g. [[416, 443]] for Oswego
Runs = list[tuple[int, int]]
```

### Spec

Made by `ask_claude`, `repair` or a viewer edit, checked by `validate_spec`. Used by `interpret`, `audit`, `widen_with_headers`. Saved as `specs/<book>.json`.

```python
class Column(TypedDict):
    # qty | unit | description | catalog | finish | mfr | notes
    field: str
    # left edge in points
    x: float

class ColumnsSpec(TypedDict):
    mode: Literal["columns"]
    # regex with group num and optional group desc
    set_header: str
    # regex matched against the first word of a row
    row_start: str
    columns: list[Column]
    # top: wrapped lines sit below the row
    # middle: wrapped lines sit above and below
    valign: Literal["top", "middle"]
    skip: list[str]
    set_meta: str | None
    note_line: str | None
    end: list[str]

class GridSpec(TypedDict):
    mode: Literal["grid"]
    # header label of the set number column, e.g. "SET"
    set_column: str
    # regex for a set number cell, e.g. "^\d+\.\d+"
    set_number: str
    # printed header label to field, e.g. {"MANUFACTURER - PRODUCT": "product"}
    columns: dict[str, str]
    # separator between mfr and catalog in a product cell
    mfr_split: str | None

Spec = ColumnsSpec | GridSpec
```

### Layout

Internal to `spec.py`. Built once per page from the calibrated spec.

```python
class Layout:
    # spec columns after calibrate, sorted by x
    cols: list[Column]
    # x where the body starts, wrapped lines must start right of it
    body_x: float
    # mfr if the book has it, else finish
    # a line with a description and this column starts a row even without a qty
    anchor_field: str | None
```

### Item

Made by `classify`, used by `resolve_top` and `resolve_middle`. One list per set per page.

```python
Item = tuple[Literal["header", "meta", "note", "anchor", "other"], Line]
```

### Component

Made by `assemble` or `run_grid`. Renamed fields in `to_result`.

```python
class Component(TypedDict):
    qty: int | None
    unit: str | None
    description: str | None
    catalog: str | None
    finish: str | None
    mfr: str | None
    notes: str | None
    page: int
    bbox: tuple[float, float, float, float]
    # active, or removed when the whole row is struck
    status: str
    # bonus fields
    confidence: dict[str, float]
    mfr_name: str | None
    finish_name: str | None
```

### HardwareSet

Made by `run_columns` and `run_grid`. Checked by `audit`, written by `to_result`.

```python
class Location(TypedDict):
    page: int
    bbox: tuple[float, float, float, float]

class HardwareSet(TypedDict):
    set_number: str
    description: str | None
    # header block lines: door numbers, "Provide each PR door(s) with the following:"
    meta: list[str]
    components: list[Component]
    # set-level prose like operational descriptions
    notes: list[str]
    # one entry per page the set appears on
    location: list[Location]
    # active | not_used | moved
    status: str
    moved_to: str | None
```

### Flag

Made by `audit`. Used by `repair`, `to_result` and the viewer.

```python
class Flag(TypedDict):
    # header_near_miss, rows_without_components, long_text_in_code_columns,
    # mfr_looks_like_finish, low_coverage, suspicious_qty
    check: str
    count: int
    # (page, line text) pairs shown to the repair call and the viewer
    examples: list[tuple[int, str]]
```

Example: `{"check": "header_near_miss", "count": 10, "examples": [[96, "Hardware Group No.103 [BULLETIN 023, 251218]"]]}`

### BookResult

Made by `to_result`. This is the output file and what the viewer and eval read.

```python
class BookResult(TypedDict):
    file: str
    # extracted | no_hardware_sets | needs_review
    status: str
    page_count: int
    # page sizes in points, so the viewer can scale bboxes
    page_size: tuple[float, float]
    # path of the spec that produced this result
    spec: str
    flags: list[Flag]
    sets: list[HardwareSet]
```

### Ground truth and score

Labeled pages in `eval/gt/`, scores made by `eval/bench.py`.

```python
class GtPage(TypedDict):
    page_image: str
    sets: list[GtSet]

class GtSet(TypedDict):
    set_number: str
    # false when the set continues from the previous page
    starts_on_page: bool
    components: list[GtComponent]

class GtComponent(TypedDict):
    qty: int | None
    description: str | None
    catalog: str | None
    finish: str | None
    mfr: str | None

class BookScore(TypedDict):
    gt_rows: int
    our_rows: int
    # rows with all five fields exact
    rows_exact: int
    gt_sets: int
    # every row exact, nothing extra, status right
    sets_full: int
    # our finish equals the label's mfr or the other way round
    swaps: int
```
