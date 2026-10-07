# the layout spec for a book, and the interpreter that applies it to every page
#
# columns mode (whitespace-aligned layouts):
#   "set_header": regex on line text, named group num (required) and desc (optional)
#   "row_start":  regex on the first word of a component row (usually the qty)
#   "columns":    [{"field": qty|unit|description|catalog|finish|mfr|notes, "x": left edge}]
#   "valign":     "top" (wrapped lines follow the row) or "middle" (wrapped lines sit above and below)
#   "skip":       regexes for lines to ignore (running headers, footers, column headings)
#   "set_meta":   regex for header-block lines before the first component (doors, "provide each...")
#   "note_line":  regex for lines that are notes on the component above
#   "end":        regexes that end the schedule
#
# grid mode (ruled tables):
#   "mode": "grid", "columns": {header label: field}, "set_column": header label,
#   "set_number": regex for a set number cell, "mfr_split": separator between mfr and catalog
import re, collections, itertools
from .lines import page_lines

SLACK = 4
CODE_FIELDS = ("mfr", "finish")
FIELDS = ("qty", "unit", "description", "catalog", "finish", "mfr", "notes")
# quantities the spec might not list: 4 digits, blanks, "As Req"
QTY_ANY = re.compile(r"^(\d{1,4}(\.0+)?|_+|-{2,3})$")
# lines that are notes, not part of a row, whatever the book
NOTE_RE = re.compile(r"^\s*(NOTES?\b|Note\b|Interlock\b|Operational\b|OPERATIONAL\b|Operation:|\*)")
# full manufacturer names, for books that print the maker inside the catalog cell and have no mfr column
MAKER_NAMES = re.compile(r"^(Von Duprin|Adams Rite|National Guard|Cavity Sliders|Ives|Horton|Schlage|LCN|Pemko|Norton|Sargent|Hager|Rockwood|McKinney|Trimco|Dorma|Falcon|Corbin Russwin|Corbin|Yale|Stanley|Best|Zero|NGP|Rixson|Glynn-Johnson|ABH|Securitron|HES|Detex|SDC|Bommer|Select)\b\s*", re.I)
FINISH_SHAPE = re.compile(r"6\d\d[A-Z]?|US\d{1,2}[A-Z]?|\d{2}[A-Z]{1,2}")
# door lists sit under a set header in allegion-style books, between these two lines
DOOR_INTRO = re.compile(r"^\s*For use on Door", re.I)
LIST_END = re.compile(r"Provide each|Each to have|with the following|^\s*QTY\b", re.I)
# a column heading row ("DESCRIPTION CATALOG NUMBER FINISH MFR") is never a component, whatever the spec says
HEADING_WORD = r"(?:QTY\.?|QT|Y|QUANTITY|UNIT|DESCRIPTION|ITEM|CATALOG|CAT\.?|NUMBER|NO\.?|#|MODEL|PRODUCT|FINISH|FIN\.?|MFR\.?|MANUFACTURER|MANF\.?|NOTES?|REMARKS|HARDWARE|TYPE)"
HEADING_RE = re.compile(rf"^\s*{HEADING_WORD}(?:\s+{HEADING_WORD})+\s*$", re.I)
DOOR_RE = re.compile(r"\b(Single|Pair)\s+(of\s+)?doors?\s*(#|\d)|\bDoor\s*#\s*\w|Opening Description", re.I)


# a bad spec fails here, before it runs over a book. returns the spec unchanged
def validate_spec(spec):
    if spec.get("mode") == "grid":
        for k in ("set_column", "set_number", "columns"):
            if k not in spec:
                raise ValueError(f"grid spec needs {k}")
        re.compile(spec["set_number"])
        return spec
    for k in ("set_header", "row_start", "columns"):
        if k not in spec:
            raise ValueError(f"spec needs {k}")
    if "num" not in re.compile(spec["set_header"]).groupindex:
        raise ValueError("set_header needs a (?P<num>...) group")
    re.compile(spec["row_start"])
    for c in spec["columns"]:
        if c["field"] not in FIELDS:
            raise ValueError(f"unknown field {c['field']}")
    for k in ("skip", "end"):
        for p in spec.get(k, []):
            re.compile(p)
    for k in ("set_meta", "note_line"):
        if spec.get(k):
            re.compile(spec[k])
    return spec


# the text the model sees when it writes a spec: each run of words tagged with its left x
#   out: "=== page 427 ===\n[80]6 [112]EA [148]HINGE [290]5BB1HW 4.5 X 4.5 - NRP AT [464]652 [508]IVE\n..."
def dump(pdf, pages, gap=8):
    out = []
    for i in pages:
        out.append(f"=== page {i} ===")
        for l in page_lines(pdf.pages[i]):
            runs, cur = [], [l["words"][0]]
            for w in l["words"][1:]:
                if w["x0"] - cur[-1]["x1"] > gap:
                    runs.append(cur); cur = [w]
                else:
                    cur.append(w)
            runs.append(cur)
            out.append(" ".join(f"[{r[0]['x0']:.0f}]" + " ".join(w["text"] for w in r) for r in runs))
    return "\n".join(out)


# the spec's columns for one page, with the helpers that decide which field a word belongs to
class Layout:
    def __init__(self, spec):
        self.cols = sorted(spec["columns"], key=lambda c: c["x"])
        self.fields = [c["field"] for c in self.cols]
        self.body_x = self.cols[1]["x"] if len(self.cols) > 1 else self.cols[0]["x"]
        self.row = re.compile(spec["row_start"])
        # the rightmost code column marks a row even when qty is missing
        self.anchor_field = next((f for f in CODE_FIELDS if f in self.fields), None)
        # right edge of each column's cells on the current page, set by measure
        self.desc_right = None
        self.right = {}

    # how far each column's text reaches on this page, which is where its cells end
    def measure(self, lines):
        edges = collections.defaultdict(list)
        for l in lines:
            if self.straddles(l):
                continue
            for w, f in zip(l["words"], self.assign(l["words"])):
                edges[f].append(w["x1"])
        self.right = {f: max(v) for f, v in edges.items() if len(v) >= 3}
        self.desc_right = self.right.get("description")

    # true when the line's first word in this column would have fit at the end of the cell above,
    # which means the line is not a wrap of that cell
    def fits_above(self, prev_lines, line, field):
        words = [w for w, f in zip(line["words"], self.assign(line["words"])) if f == field]
        if not words:
            return None
        for l in reversed(prev_lines):
            above = [w for w, f in zip(l["words"], self.assign(l["words"])) if f == field]
            if above:
                right = self.right.get(field, above[-1]["x1"] + 200)
                return right - above[-1]["x1"] >= (words[0]["x1"] - words[0]["x0"]) + 8
        return True

    # the column whose left edge is the last one at or before x
    def field(self, x):
        k = max((j for j, c in enumerate(self.cols) if c["x"] <= x + SLACK), default=0)
        return self.fields[k]

    # one field per word, by x. a word that continues a run of text (no gap before it) cannot jump
    # into a code column, so "4.5 X 4.5 NRP" stays in catalog even where NRP sits past the finish edge
    #   in:  words of "6 EA HINGE 5BB1HW 4.5 X 4.5 NRP 652 IVE" on oswego's columns
    #   out: ["qty", "unit", "description", "catalog", "catalog", "catalog", "catalog", "catalog", "finish", "mfr"]
    def assign(self, words, gap=4):
        out, prev = [], None
        for w in words:
            f = self.field(w["x0"])
            if prev and f != out[-1] and w["x0"] - prev["x1"] < gap and (f in CODE_FIELDS or w["x0"] < self.cols[self.fields.index(f)]["x"]):
                f = out[-1]
            out.append(f)
            prev = w
        return out

    def filled(self, line):
        return set(self.assign(line["words"]))

    def cells(self, line):
        out = collections.defaultdict(list)
        for w, f in zip(line["words"], self.assign(line["words"])):
            out[f].append(w["text"])
        return out

    # does the line open with a quantity in the first column
    def qty_start(self, line):
        ws = line["words"]
        if self.field(ws[0]["x0"]) != self.fields[0] or len(ws) < 2:
            return False
        t = ws[0]["text"]
        return bool(self.row.match(t) or QTY_ANY.match(t) or (t.lower() == "as" and ws[1]["text"].lower().startswith("req")))

    # does the line start a component: a qty in the first column, or a description plus a code
    # column aligned to the grid. door lists and door descriptions are header lines, not rows
    def is_anchor(self, line):
        c = self.cells(line)
        desc = " ".join(c.get("description", []))
        if DOOR_RE.search(line["text"]) or (desc and not re.search(r"[A-Za-z]{3}", desc) and not any(c.get(f) for f in CODE_FIELDS)):
            return False
        if self.qty_start(line):
            return True
        f = set(c)
        return self.anchor_field in f and "description" in f and self.aligned(line)

    # a line continues the row above only if its first description word would not have fit there
    #   "6 HINGE 5BB1HW 4.5 X 4.5 - NRP AT" then "OUTSWINGING DRS" under catalog -> True
    def wraps(self, prev_lines, line):
        c = self.assign(line["words"])
        first = next((w for w, f in zip(line["words"], c) if f == "description"), None)
        if first is None:
            return True
        above = None
        for l in reversed(prev_lines):
            ws = [w for w, f in zip(l["words"], self.assign(l["words"])) if f == "description"]
            if ws:
                above = ws[-1]
                break
        if above is None:
            return False
        # the cell ends where this page's description text reaches, not at the next column, since cells have a gutter
        right = self.desc_right or next((col["x"] for col in self.cols if col["x"] > above["x1"] + 1), above["x1"] + 200)
        return right - above["x1"] < (first["x1"] - first["x0"]) + 8

    # prose runs straight across column edges, table cells stop short of them
    def straddles(self, line):
        return any(w["x0"] < c["x"] - SLACK < w["x1"] for w in line["words"] for c in self.cols[1:])

    def aligned(self, line, gap=8):
        ws = line["words"]
        return not self.straddles(line) and any(b["x0"] - a["x1"] > gap for a, b in zip(ws, ws[1:]))


# the spec fixes column order and roles, each page's own aligned word edges fix the positions.
# catches a column that drifts a few points between pages (star page 85)
#   in:  spec columns catalog 240, finish 470, mfr 497; this page's rows start cells at 243, 471, 499
#   out: the same spec with catalog 242, finish 470, mfr 498
def calibrate(spec, lines, reach=45, share=0.25):
    row = re.compile(spec["row_start"])
    cols = sorted(spec["columns"], key=lambda c: c["x"])
    rows = [l for l in lines if (row.match(l["words"][0]["text"]) or QTY_ANY.match(l["words"][0]["text"]))
            and abs(l["words"][0]["x0"] - cols[0]["x"]) < 15]
    if len(rows) < 3:
        return spec
    starts = []
    for l in rows:
        starts += sorted({l["words"][0]["x0"]} | {b["x0"] for a, b in zip(l["words"], l["words"][1:]) if b["x0"] - a["x1"] > 6})
    # edges a couple of points apart are one column printed with a slightly different offset
    clusters = []
    for x in sorted(starts):
        if clusters and x - clusters[-1][-1] <= 3:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    support = {min(c): len(c) / len(rows) for c in clusters if len(c) >= share * len(rows)}
    code = [c for c in cols[1:] if c["field"] in ("catalog", "finish", "mfr", "notes")]
    cands = [[p for p in support if abs(p - c["x"]) <= reach and p > cols[0]["x"]] + [None] for c in code]
    # pick one edge per code column, in order, favoring edges many rows share
    best = None
    for combo in itertools.product(*cands):
        xs = [p if p is not None else c["x"] + 1 for p, c in zip(combo, code)]
        if any(b <= a for a, b in zip(xs, xs[1:])):
            continue
        score = sum(support[p] for p in combo if p is not None) - 0.002 * sum(abs(x - c["x"]) for x, c in zip(xs, code))
        if best is None or score > best[0]:
            best = (score, combo)
    chosen = {c["field"]: p for c, p in zip(code, best[1])} if best else {}
    new = []
    for c in cols:
        p = chosen.get(c["field"])
        new.append({**c, "x": p - 1} if p is not None else c)
    return {**spec, "columns": new}


def box(lines):
    return [round(min(l["x0"] for l in lines), 1), round(min(l["top"] for l in lines), 1),
            round(max(l["x1"] for l in lines), 1), round(max(l["bottom"] for l in lines), 1)]


# "3", "3.0", "2571" -> int; blank, "__", "--", "As Req" -> None, never a guess
def parse_qty(q):
    return int(float(q)) if q and re.fullmatch(r"\d{1,4}(\.0+)?", q) else None


# one component from its anchor line plus its wrapped lines
#   in:  "6 EA HINGE 5BB1HW 4.5 X 4.5 - NRP AT 652 IVE" and the wrap "OUTSWINGING DRS"
#   out: {"qty": 6, "unit": "EA", "description": "HINGE", "catalog": "5BB1HW 4.5 X 4.5 - NRP AT OUTSWINGING DRS",
#         "finish": "652", "mfr": "IVE", "notes": None, "bbox": [80.1, 98.2, 528.0, 121.7]}
def assemble(layout, anchor, extra):
    comp = {f: [] for f in layout.fields}
    for l in sorted([anchor] + extra, key=lambda l: l["top"]):
        for w, f in zip(l["words"], layout.assign(l["words"])):
            comp[f].append(w["text"])
    # a code split over two lines ("I" "VE") is one code
    for f in CODE_FIELDS:
        if f in comp and len(comp[f]) > 1 and all(len(t) <= 3 and t.isalpha() for t in comp[f]):
            comp[f] = ["".join(comp[f])]
    # a cell line ending in a hyphen continues the same token on the next line
    comp = {k: (re.sub(r"(?<=\w-) (?=\S)", "", " ".join(v)) or None) for k, v in comp.items()}
    for k, v in comp.items():
        # dash placeholders mean the cell is empty
        if v and re.fullmatch(r"-{1,3}", v):
            comp[k] = None
    # "Von Duprin 98NL" in a book with no mfr column: the maker is the mfr
    if "mfr" not in layout.fields and comp.get("catalog"):
        m = MAKER_NAMES.match(comp["catalog"])
        if m and comp["catalog"][m.end():].strip():
            comp["mfr"], comp["catalog"] = m.group(1), comp["catalog"][m.end():].strip()
    # a lone finish-shaped value in the mfr column with no finish is the finish, and "622 SC" is both
    if comp.get("mfr") and not comp.get("finish") and "finish" in layout.fields:
        if FINISH_SHAPE.fullmatch(comp["mfr"]):
            comp["finish"], comp["mfr"] = comp["mfr"], None
        else:
            m = re.fullmatch(rf"({FINISH_SHAPE.pattern})\s+([A-Z]{{2,4}})", comp["mfr"])
            if m:
                comp["finish"], comp["mfr"] = m.group(1), m.group(2)
    comp["qty"] = parse_qty(comp.get("qty"))
    comp["bbox"] = box([anchor] + extra)
    # how the row was read, for the confidence scores: lines it spans, whether a qty anchored it, column snapping
    comp["_evidence"] = {"lines": 1 + len(extra), "qty_row": layout.qty_start(anchor), "calibrated": getattr(layout, "calibrated", False),
                         "snapped": sorted(getattr(layout, "snapped", ()))}
    return comp


# vertically centered cells: lines of one row overlap vertically, rows are separated by a gap
def resolve_middle(layout, items):
    groups, notes = [], []
    for kind, l in items:
        if kind == "note":
            if groups:
                groups[-1][1].append(l["text"])
            else:
                notes.append(l["text"])
        elif groups and l["top"] < max(x["bottom"] for x in groups[-1][0]) - 0.5:
            groups[-1][0].append(l)
        else:
            groups.append(([l], []))
    out = []
    for g, g_notes in groups:
        filled = set().union(*(layout.filled(l) for l in g))
        is_row = any(layout.is_anchor(l) for l in g) or (
            "description" in filled and filled - {"description"} and not any(layout.straddles(l) for l in g))
        if is_row:
            c = assemble(layout, g[0], g[1:])
            if g_notes:
                c["notes"] = " ".join(filter(None, [c.get("notes")] + g_notes))
            out.append(c)
        else:
            notes += [l["text"] for l in g] + g_notes
    return out, notes


# the tagged lines of one set on one page -> (components, set notes)
#   in:  [("anchor", "6 EA HINGE 5BB1HW ... 652 IVE"), ("other", "OUTSWINGING DRS"),
#         ("anchor", "1 EA CLOSER 4040XP 689 LCN"), ("other", "OPERATIONAL DESCRIPTION: ...")]
#   out: ([hinge component with the wrap folded in, closer component], ["OPERATIONAL DESCRIPTION: ..."])
def resolve(layout, valign, items):
    if valign == "middle":
        return resolve_middle(layout, items)
    rows, notes = [], []
    cur, prev, in_note, pending = None, None, False, []
    prev_kind = None
    for idx, (kind, l) in enumerate(items):
        h = l["bottom"] - l["top"]
        close = prev is not None and l["top"] - prev["bottom"] < 1.2 * h
        nxt = items[idx + 1] if idx + 1 < len(items) else None
        if kind == "anchor":
            cur = {"lines": pending + [l], "notes": []}
            pending = []
            rows.append(cur)
            in_note = False
        elif kind == "other" and nxt is not None and nxt[0] == "anchor" and nxt[1]["top"] - l["bottom"] < 1.2 * h \
                and l["x0"] >= layout.body_x - SLACK and not (layout.filled(l) & layout.filled(nxt[1])) \
                and not NOTE_RE.match(l["text"]) and (cur is None or all(
                    layout.fits_above(cur["lines"], l, f) is not False for f in layout.filled(l))):
            # a centered cell: this line sits just above a row whose own line is empty in these columns,
            # and it would have fit in the row above, so it is not that row's wrap
            pending.append(l)
        elif kind == "note" or (kind == "other" and NOTE_RE.match(l["text"])) or (kind == "other" and in_note and close):
            (cur["notes"] if cur is not None else notes).append(l["text"])
            in_note = True
        elif kind == "other" and l["x0"] >= layout.body_x - SLACK and cur is not None and close and (
                layout.filled(l) == {"description"} and prev_kind in ("anchor", "wrap") or layout.wraps(cur["lines"], l)):
            # text only in the description column, tight under a row, is that row's wrapped description
            cur["lines"].append(l)
        elif kind == "other" and l["x0"] >= layout.body_x - SLACK and "description" in layout.filled(l) \
                and layout.filled(l) - {"description", "qty", "unit"} and layout.aligned(l) and not DOOR_RE.search(l["text"]) \
                and (layout.filled(l) & set(CODE_FIELDS) or len(layout.cells(l)["description"]) >= 2 or prev_kind == "anchor"):
            # its own description plus another cell, but not a wrap: a row with no quantity
            cur = {"lines": [l], "notes": []}
            rows.append(cur)
            in_note = False
        else:
            notes.append(l["text"])
            cur, in_note = None, False
        # what this line became, for the next line's decision
        prev_kind = "anchor" if kind == "anchor" or (cur is not None and cur["lines"] and cur["lines"][-1] is l and len(cur["lines"]) == 1) else ("wrap" if cur is not None and cur["lines"] and cur["lines"][-1] is l else kind)
        prev = l
    comps = []
    for r in rows:
        c = assemble(layout, r["lines"][0], r["lines"][1:])
        if r["notes"]:
            c["notes"] = " ".join(filter(None, [c.get("notes")] + r["notes"]))
        comps.append(c)
    return comps, notes


# walk the pages in order, start a set at each header, tag every other line, resolve once per page
#   out: [{"set_number": "18", "description": None, "meta": ["E120A E121B"], "components": [...],
#          "notes": [], "location": [{"page": 427, "bbox": [72.0, 73.5, 530.2, 630.5]}]}, ...]
def run_columns(spec, pdf, pages):
    layout = Layout(spec)
    hdr = re.compile(spec["set_header"])
    skip = [re.compile(p) for p in spec.get("skip", [])]
    meta = re.compile(spec["set_meta"]) if spec.get("set_meta") else None
    note = re.compile(spec["note_line"]) if spec.get("note_line") else None
    end = [re.compile(p) for p in spec.get("end", [])]
    valign = spec.get("valign", "top")
    sets, cur, buf = [], None, []
    in_doors = False

    # resolve the lines buffered for the current set on this page
    def flush(page):
        nonlocal buf
        if cur is not None and buf:
            comps, notes = resolve(layout, valign, buf)
            for c in comps:
                c["page"] = page
            cur["components"] += comps
            cur["notes"] += notes
            cur["location"].append({"page": page, "bbox": box([l for _, l in buf])})
        buf = []

    for i in pages:
        page = page_lines(pdf.pages[i])
        cal = calibrate(spec, page)
        layout = Layout(cal)
        # what the calibration did on this page, kept as evidence for the confidence scores
        layout.calibrated = cal is not spec
        layout.snapped = {c["field"] for c, o in zip(sorted(cal["columns"], key=lambda c: c["x"]), sorted(spec["columns"], key=lambda c: c["x"])) if c["x"] != o["x"]}
        kept = []
        for l in page:
            # a struck row is a revision, drop it. struck words inside a row are dropped too
            struck = [w.get("struck") for w in l["words"]]
            if any(struck):
                if struck[0] or sum(struck) > len(struck) / 2:
                    continue
                l = dict(l, words=[w for w in l["words"] if not w.get("struck")])
                l["text"] = " ".join(w["text"] for w in l["words"])
                l["x0"], l["x1"] = l["words"][0]["x0"], max(w["x1"] for w in l["words"])
            kept.append(l)
        layout.measure(kept)
        for l in kept:
            t = l["text"]
            if HEADING_RE.match(t) or any(p.search(t) for p in skip):
                continue
            if any(p.search(t) for p in end):
                # a book can hold several schedules: end closes the current set, the next header reopens
                flush(i)
                cur = None
                continue
            m = hdr.search(t)
            if m:
                flush(i)
                num, desc = m.group("num").strip(), (m.groupdict().get("desc") or "").strip()
                # "Set #AL 01": an all-letter number followed by a digit token is one number
                dm = re.match(r"^(\d[\w.\-]*)(?:\s+|$)", desc)
                if re.fullmatch(r"[A-Za-z]{1,4}", num) and dm:
                    num, desc = f"{num} {dm.group(1)}", desc[dm.end():].strip()
                cur = {"set_number": num, "description": desc or None,
                       "meta": [], "components": [], "notes": [], "location": []}
                sets.append(cur)
                buf = [("header", l)]
                in_doors = False
                continue
            if cur is None:
                continue
            if DOOR_INTRO.search(t) and not cur["components"]:
                cur["meta"].append(t); buf.append(("header", l)); in_doors = True
                continue
            if in_doors:
                cur["meta"].append(t); buf.append(("header", l))
                if LIST_END.search(t) or len(cur["meta"]) > 15:
                    in_doors = False
                continue
            if meta and meta.search(t) and not cur["components"] and not any(k == "anchor" for k, _ in buf):
                cur["meta"].append(t); buf.append(("header", l))
            elif note and note.search(t):
                buf.append(("note", l))
            elif layout.is_anchor(l):
                buf.append(("anchor", l))
            else:
                buf.append(("other", l))
        flush(i)
    # an empty set that says where it went, or that it is not used
    for s in sets:
        text = " ".join([s["description"] or ""] + s["notes"] + s["meta"])
        moved = re.search(r"moved to .*?set\s*(?:HW\s*)?#?\s*([A-Z0-9][\w.-]*)", text, re.I)
        if not s["components"] and moved:
            s["status"], s["moved_to"] = "moved", moved.group(1)
        elif not s["components"] and re.search(r"NOT USED|N/A", text, re.I):
            s["status"] = "not_used"
    return sets


# ruled tables: pdfplumber finds the cells, the header row maps printed labels to fields,
# a cell matching set_number starts a set, other text in that column is the set's description
#   in:  roselle, columns {"HARDWARE TYPE": "description", "MANUFACTURER - PRODUCT": "product", "QTY.": "qty", ...}
#   out: sets like run_columns, with "IVES - 5BB1 4.5 x 4.5" split into mfr IVES and catalog 5BB1 4.5 x 4.5
def run_grid(spec, pdf, pages):
    num_re = re.compile(spec["set_number"])
    sets, cur = [], None
    for i in pages:
        for t in pdf.pages[i].find_tables():
            rows = t.rows
            data = t.extract()
            colmap = None
            for r, cells in zip(rows, data):
                cells = [(c or "").replace("\n", " ").strip() for c in cells]
                if colmap is None:
                    labels = [c.upper() for c in cells]
                    if spec["set_column"].upper() in labels:
                        colmap = {}
                        for lab, field in spec["columns"].items():
                            if lab.upper() in labels:
                                colmap[field] = labels.index(lab.upper())
                        set_col = labels.index(spec["set_column"].upper())
                    continue
                get = lambda f: cells[colmap[f]] if f in colmap and colmap[f] < len(cells) else ""
                setcell = cells[set_col]
                m = num_re.match(setcell)
                if m:
                    cur = {"set_number": m.group(0), "description": setcell[m.end():].strip() or None,
                           "meta": [], "components": [], "notes": [], "location": []}
                    sets.append(cur)
                elif setcell and cur is not None:
                    cur["description"] = " ".join(filter(None, [cur["description"], setcell]))
                if cur is None:
                    continue
                bbox = [round(v, 1) for v in r.bbox]
                if not cur["location"] or cur["location"][-1]["page"] != i:
                    cur["location"].append({"page": i, "bbox": bbox})
                else:
                    b = cur["location"][-1]["bbox"]
                    cur["location"][-1]["bbox"] = [min(b[0], bbox[0]), min(b[1], bbox[1]), max(b[2], bbox[2]), max(b[3], bbox[3])]
                desc, product = get("description"), get("product")
                if desc or product:
                    mfr, cat = None, product or None
                    sep = spec.get("mfr_split")
                    if sep and product and sep in product:
                        mfr, cat = (s.strip() for s in product.split(sep, 1))
                    cur["components"].append({"qty": parse_qty(get("qty")), "description": desc or None,
                                              "catalog": cat, "mfr": mfr, "finish": get("finish") or None,
                                              "notes": get("notes") or None, "bbox": bbox, "page": i, "_evidence": {"grid": True}})
                elif get("notes") and cur["components"]:
                    c = cur["components"][-1]
                    c["notes"] = " ".join(filter(None, [c["notes"], get("notes")]))
    return sets


# spec + open pdfplumber pdf + 0-based page list -> sets
def interpret(spec, pdf, pages):
    return (run_grid if spec.get("mode") == "grid" else run_columns)(spec, pdf, pages)
