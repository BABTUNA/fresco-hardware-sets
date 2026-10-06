# Hardware sets: backend implementation

Companion to [PLAN.md](PLAN.md). The viewer is in [IMPLEMENTATION_FRONTEND.md](IMPLEMENTATION_FRONTEND.md). Function and file names here are the target names for `hwsets/`. The same logic already runs in `experiments/` under older names, listed in the files table.

## 0. Status

| Part | State |
| :--- | :--- |
| Finder, lines, interpreter, audit | Done in `experiments/`, benchmarked, needs porting and cleanup |
| Spec compile and repair calls | The prompt exists (`experiments/SPEC_PROMPT.md`), a Claude subagent stood in for the API call. `compile.py` is new code |
| Output schema, `extract.py`, `cli.py` | New |
| Eval | Done, strict scorer in `experiments/bench.py`, 155 labeled pages plus 25 held out |
| Legends, confidence | Not started (bonus) |

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
hwsets extract book.pdf -o out.json                                  cli.py
└─ extract_book(pdf_path, spec_dir)                                  extract.py
   ├─ find_schedule(pdf_path) -> texts, scores, runs                 finder.py
   │  ├─ page_texts(pdf_path)                                        finder.py
   │  ├─ row_like(text_line)                                         finder.py
   │  └─ group_runs(scores, vocab)                                   finder.py
   ├─ if no runs: return BookResult(status="no_hardware_sets")       extract.py
   ├─ load_or_compile(pdf_path, runs, scores, spec_dir) -> Spec      compile.py
   │  ├─ pick_samples(runs, scores)                                  compile.py
   │  ├─ dump(pdf, pages)                                            compile.py
   │  │  └─ page_lines(page)                                         lines.py
   │  ├─ ask_claude(SPEC_PROMPT, dump)                               compile.py
   │  └─ validate_spec(raw)                                          spec.py
   ├─ widen_with_headers(spec, texts, runs) -> pages                 finder.py
   ├─ interpret(spec, pdf, pages) -> list[HardwareSet]               spec.py
   │  ├─ run_columns(spec, pdf, pages)                               spec.py
   │  │  ├─ page_lines(page)                                         lines.py
   │  │  │  └─ mark_struck(words, page)                              lines.py
   │  │  ├─ calibrate(spec, lines)                                   spec.py
   │  │  ├─ classify(line, layout)                                   spec.py
   │  │  ├─ resolve_top(layout, items)                               spec.py
   │  │  ├─ resolve_middle(layout, items)                            spec.py
   │  │  │  └─ assemble(layout, anchor, extra) -> Component          spec.py
   │  │  │     ├─ Layout.assign(words)                               spec.py
   │  │  │     └─ parse_qty(text)                                    spec.py
   │  │  └─ set_status(hardware_set)                                 spec.py
   │  └─ run_grid(spec, pdf, pages)                                  spec.py
   │     └─ split_mfr(product, sep)                                  spec.py
   ├─ audit(spec, sets, texts, pages, scores) -> list[Flag]          audit.py
   │  ├─ header_near_miss                                            audit.py
   │  ├─ rows_without_components                                     audit.py
   │  ├─ long_text_in_code_columns                                   audit.py
   │  ├─ mfr_looks_like_finish                                       audit.py
   │  ├─ low_coverage                                                audit.py
   │  └─ suspicious_qty                                              audit.py
   ├─ if flags: repair(spec, flags, dump) -> Spec                    compile.py
   │  └─ interpret + audit again, once                               spec.py, audit.py
   ├─ read_legends(pdf, pages) -> Legend                             legend.py
   ├─ confidence(component, layout, flags)                           extract.py
   └─ to_result(sets, flags, pdf, spec) -> BookResult                extract.py
```

| Call | What it does |
| :--- | :--- |
| `extract_book` | Runs the whole pipeline for one PDF and returns a `BookResult`. The only function the CLI, viewer and eval call. |
| `find_schedule` | Scores every page and returns the page runs that hold schedules. |
| `page_texts` | Fast text extraction with pypdfium2, one list of text lines per page. Used for scoring and header search, not for coordinates. |
| `row_like` | True when a line looks like a component row: qty, words, short codes at the end, or a hardware word next to a finish code (grid tables). |
| `group_runs` | Joins pages with 2+ row-like lines into runs, allowing 1-page gaps. Keeps a run only if it has 5+ rows and 3+ hardware words, which drops other trades' equipment lists. |
| `load_or_compile` | Returns `specs/<book>.json` if it exists. Otherwise compiles a new spec and saves it. |
| `pick_samples` | The 2 pages in the runs with the most row-like lines. |
| `dump` | Renders pages as text where each run of words is tagged with its left x, e.g. `[80]6 [112]EA [148]HINGE [290]5BB1HW 4.5 X 4.5 [464]652 [508]IVE`. This is all the model sees. |
| `page_lines` | pdfplumber words grouped into visual lines with coordinates. Drops rotated watermark text and private-use icon glyphs. |
| `ask_claude` | One Anthropic API call with the spec prompt and the dump. Returns the spec JSON. |
| `validate_spec` | Checks the reply against the spec schema and compiles the regexes, so a bad spec fails loudly before it runs. |
| `widen_with_headers` | Runs the spec's `set_header` regex over every page's text and adds header pages near the runs, then fills gaps of up to 3 pages. Catches sets the finder scored low (JC Ryan's EX sets). |
| `interpret` | Picks `run_columns` or `run_grid` from the spec's mode. |
| `run_columns` | Walks the pages in order. Starts a set at each header, tags every other line, and resolves the tagged lines into components once per page. |
| `mark_struck` | Marks words crossed by a thin horizontal line at mid-height. A fully struck row is kept with status `removed`. Struck words inside a row are dropped. |
| `calibrate` | Re-snaps the catalog, finish, mfr and notes columns to this page's own aligned word edges, within 30pt of the spec's x. Fixes drift like Star page 85. |
| `classify` | Tags a line as `header`, `meta` (door list, "Provide each..."), `note`, `anchor` (starts a component) or `other`. |
| `resolve_top` | Wrapped lines sit below their row. Each `other` line joins the anchor above it if the vertical gap is small, otherwise it becomes a set note. |
| `resolve_middle` | Wrapped lines sit above and below their row. Lines that overlap vertically are one row, a positive gap starts a new row. |
| `assemble` | Builds one `Component` from an anchor line plus its wrapped lines: fields by x, hyphen joins across line breaks, `---` to null, bbox. |
| `Layout.assign` | Maps each word to a field by x. A word that continues a run of text without a gap cannot jump into the finish or mfr column. |
| `parse_qty` | `"3"` and `"3.0"` become 3. Blank, `__`, `--`, `As Req` become null. |
| `set_status` | `moved` with `moved_to` for "Moved to Exterior Set HW E14", `not_used` for NOT USED or N/A, else `active`. |
| `run_grid` | Ruled tables. pdfplumber finds the table, the header row maps labels to fields, a cell matching `set_number` starts a set, other text in that column becomes the description. |
| `split_mfr` | `"IVES - 5BB1 4.5\" x 4.5\""` becomes mfr `IVES`, catalog `5BB1 4.5" x 4.5"`. |
| `audit` | Runs every check and returns the flags. |
| `header_near_miss` | Lines that start like the header (`Set:`, `Hardware Group No.`) but did not match it. Caught HFH's 10 merged sets and Star's plural variants. |
| `rows_without_components` | Pages with 3+ row-like lines and no extracted components. |
| `long_text_in_code_columns` | More than 10% of components have 4+ words in finish or mfr, so a column x is wrong. |
| `mfr_looks_like_finish` | The mfr column is mostly finish-shaped values (626, US26D, BLK). Means the columns are swapped. |
| `low_coverage` | Fewer than 60% as many components as row-like lines. |
| `suspicious_qty` | Qty over 99 with no catalog, like Lyons' door-number line read as qty 115. |
| `repair` | One Claude call with the spec, the flags with example lines, and the same dump. Returns a revised spec. If flags remain after it, the book is `needs_review`. |
| `read_legends` | Bonus. Parses code/name lists printed in the book (`HA Hager`, `C Charcoal`) into a lookup. |
| `confidence` | Bonus. Per-field score from evidence already in hand: did the column snap on this page, does the value fit its column's shape, did the set pass the audit. |
| `to_result` | Converts to the output schema: 1-based pages, `catalog` renamed to `catalog_number`, legend names added, book status set. |

### Score against the labels

```
python -m eval.bench                                                  eval/bench.py
└─ for each eval/gt/<book>_p<page>.json
   ├─ load BookResult for the book, keep the sets on this page       eval/bench.py
   ├─ match_sets(gt_sets, our_sets)                                  eval/bench.py
   └─ for each matched set: match_rows(gt_rows, our_rows)            eval/bench.py
      └─ norm(value) per field                                       eval/bench.py
```

| Call | What it does |
| :--- | :--- |
| `match_sets` | Pairs labeled sets with ours by set number on the same page. A labeled set with no partner counts every row as missed. |
| `match_rows` | A row counts only when all five fields (qty, description, catalog, finish, mfr) are exact after `norm`. Rows are a multiset, so two identical labeled rows need two identical extracted rows. Extra rows count against precision. |
| `norm` | Case, whitespace, curly quotes and dash variants. Nothing fuzzier. |
| set fully correct | Every row matched, nothing extra, status right. |
| swap | Our finish equals the label's mfr or the other way round. |

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

### Flow

| Structure | Made by | Used by |
| :--- | :--- | :--- |
| `Word`, `Line` | `page_lines` | `dump`, `calibrate`, `classify`, `resolve_*`, `assemble` |
| `Runs` | `group_runs` | `load_or_compile`, `widen_with_headers` |
| `Spec` | `ask_claude`, `repair`, viewer edit | `interpret`, `audit`, `widen_with_headers` |
| `Layout` | `run_columns` per page | `classify`, `resolve_*`, `assemble` |
| `Item` | `classify` | `resolve_top`, `resolve_middle` |
| `Component` | `assemble`, `run_grid` | `HardwareSet`, `confidence`, `to_result` |
| `HardwareSet` | `run_columns`, `run_grid` | `audit`, `to_result` |
| `Flag` | `audit` | `repair`, `to_result`, viewer |
| `BookResult` | `to_result` | output file, viewer, `eval/bench.py` |
