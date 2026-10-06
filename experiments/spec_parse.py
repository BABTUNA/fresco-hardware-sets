# exp 3/4: run a small per-book layout spec over pages deterministically
#
# columns mode spec:
#   "set_header": regex on line text, named group num (required) and desc (optional)
#   "row_start":  regex on the first word of a component row (usually the qty)
#   "columns":    [{"field": qty|unit|description|catalog|finish|mfr|notes, "x": left edge}]
#   "valign":     "top" (wrapped lines follow the row) or "middle" (wrapped lines sit above and below)
#   "skip":       regexes for lines to ignore (running headers, footers, column headings)
#   "set_meta":   regex for header-block lines before the first component (doors, "provide each...")
#   "note_line":  regex for lines that are notes on the component above
#   "end":        regexes that end the schedule
#
# grid mode spec (ruled tables):
#   "mode": "grid", "columns": {header label: field}, "set_column": header label,
#   "set_number": regex for a set number cell, "mfr_split": separator between mfr and catalog
import re, sys, json, collections
import pdfplumber
from lines import page_lines

SLACK = 4
CODE_FIELDS = ("mfr", "finish")
# quantities the spec might not list: 4 digits, blanks, "As Req"
QTY_ANY = re.compile(r"^(\d{1,4}(\.0+)?|_+|-{2,3})$")
# lines that are notes, not part of a row, whatever the book
NOTE_RE = re.compile(r"^\s*(NOTES?\b|Note\b|Interlock\b|Operational\b|OPERATIONAL\b|Operation:|\*)")
# door and opening lines sit under a set header but are not hardware
# allegion-style books list door numbers between these two lines
DOOR_INTRO = re.compile(r"^\s*For use on Door", re.I)
LIST_END = re.compile(r"Provide each|Each to have|with the following|^\s*QTY\b", re.I)
DOOR_RE = re.compile(r"\b(Single|Pair)\s+(of\s+)?Doors?\b|\bDoor\s*#\s*\w|Opening Description", re.I)


def dump(pdf, pages, gap=8):
    # compact text view for the model: each run of words tagged with its left x
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


class Layout:
    def __init__(self, spec):
        self.cols = sorted(spec["columns"], key=lambda c: c["x"])
        self.fields = [c["field"] for c in self.cols]
        self.body_x = self.cols[1]["x"] if len(self.cols) > 1 else self.cols[0]["x"]
        self.row = re.compile(spec["row_start"])
        # the rightmost code column marks a row even when qty is missing
        self.anchor_field = next((f for f in CODE_FIELDS if f in self.fields), None)
        # right edge of each column's cells on the current page, set per page
        self.desc_right = None
        self.right = {}

    def measure(self, lines):
        # how far each column's text reaches on this page, which is where its cells end
        edges = collections.defaultdict(list)
        for l in lines:
            if self.straddles(l):
                continue
            for w, f in zip(l["words"], self.assign(l["words"])):
                edges[f].append(w["x1"])
        self.right = {f: max(v) for f, v in edges.items() if len(v) >= 3}
        self.desc_right = self.right.get("description")

    def fits_above(self, prev_lines, line, field):
        # true when the line's first word in this column would have fit at the end of the cell above,
        # which means the line is not a wrap of that cell
        words = [w for w, f in zip(line["words"], self.assign(line["words"])) if f == field]
        if not words:
            return None
        for l in reversed(prev_lines):
            above = [w for w, f in zip(l["words"], self.assign(l["words"])) if f == field]
            if above:
                right = self.right.get(field, above[-1]["x1"] + 200)
                return right - above[-1]["x1"] >= (words[0]["x1"] - words[0]["x0"]) + 8
        return True

    def field(self, x):
        k = max((j for j, c in enumerate(self.cols) if c["x"] <= x + SLACK), default=0)
        return self.fields[k]

    def assign(self, words, gap=4):
        # a word that continues a run of text cannot jump into a code column; cells are split by whitespace
        out, prev = [], None
        for w in words:
            f = self.field(w["x0"])
            if prev and f in CODE_FIELDS and out[-1] not in CODE_FIELDS and w["x0"] - prev["x1"] < gap:
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

    def qty_start(self, line):
        ws = line["words"]
        if self.field(ws[0]["x0"]) != self.fields[0] or len(ws) < 2:
            return False
        t = ws[0]["text"]
        return bool(self.row.match(t) or QTY_ANY.match(t) or (t.lower() == "as" and ws[1]["text"].lower().startswith("req")))

    def is_anchor(self, line):
        c = self.cells(line)
        desc = " ".join(c.get("description", []))
        # door lists and door descriptions are header lines, and a row needs a real word in its description
        if DOOR_RE.search(line["text"]) or (desc and not re.search(r"[A-Za-z]{3}", desc) and not any(c.get(f) for f in CODE_FIELDS)):
            return False
        if self.qty_start(line):
            return True
        f = set(c)
        return self.anchor_field in f and "description" in f and self.aligned(line)

    def wraps(self, prev_lines, line):
        # a line continues the row above only if its first description word would not have fit there
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

    def straddles(self, line):
        # prose runs straight across column edges; table cells stop short of them
        return any(w["x0"] < c["x"] - SLACK < w["x1"] for w in line["words"] for c in self.cols[1:])

    def aligned(self, line, gap=8):
        ws = line["words"]
        return not self.straddles(line) and any(b["x0"] - a["x1"] > gap for a, b in zip(ws, ws[1:]))


def calibrate(spec, lines, reach=45, share=0.25):
    # the spec fixes column order and roles; each page's own aligned edges fix the positions
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
    peaks = [min(c) for c in clusters if len(c) >= share * len(rows)]
    new, floor = [cols[0]], cols[0]["x"]
    for c in cols[1:]:
        if c["field"] not in ("catalog", "finish", "mfr", "notes"):
            # qty, unit and description often share one run of text, so they have no edge to snap to
            new.append(c); floor = c["x"]; continue
        near = [p for p in peaks if abs(p - c["x"]) <= reach and p - 1 > floor]
        x = min(near, key=lambda p: abs(p - c["x"])) - 1 if near else c["x"]
        new.append({**c, "x": x})
        floor = x
    return {**spec, "columns": new}


def _box(lines):
    return [round(min(l["x0"] for l in lines), 1), round(min(l["top"] for l in lines), 1),
            round(max(l["x1"] for l in lines), 1), round(max(l["bottom"] for l in lines), 1)]


def _qty(q):
    # "3", "3.0", "2571" -> int; blanks, "__", "As Req" -> None
    return int(float(q)) if q and re.fullmatch(r"\d{1,4}(\.0+)?", q) else None


def _assemble(layout, anchor, extra):
    comp = {f: [] for f in layout.fields}
    for l in sorted([anchor] + extra, key=lambda l: l["top"]):
        for w, f in zip(l["words"], layout.assign(l["words"])):
            comp[f].append(w["text"])
    # a cell line ending in a hyphen continues the same token on the next line
    comp = {k: (re.sub(r"(?<=\w-) (?=\S)", "", " ".join(v)) or None) for k, v in comp.items()}
    for k, v in comp.items():
        # dash placeholders mean the cell is empty
        if v and re.fullmatch(r"-{1,3}", v):
            comp[k] = None
    comp["qty"] = _qty(comp.get("qty"))
    comp["bbox"] = _box([anchor] + extra)
    return comp


def _resolve_middle(layout, items):
    # vertically centered cells: lines of one row overlap vertically, rows are separated by a gap
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
            c = _assemble(layout, g[0], g[1:])
            if g_notes:
                c["notes"] = " ".join(filter(None, [c.get("notes")] + g_notes))
            out.append(c)
        else:
            notes += [l["text"] for l in g] + g_notes
    return out, notes


def _resolve(layout, valign, items):
    # items: list of (kind, line) for one set on one page, in reading order
    if valign == "middle":
        return _resolve_middle(layout, items)
    rows, notes = [], []
    cur, prev, in_note, pending = None, None, False, []
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
        elif kind == "other" and l["x0"] >= layout.body_x - SLACK and cur is not None and close and layout.wraps(cur["lines"], l):
            cur["lines"].append(l)
        elif kind == "other" and l["x0"] >= layout.body_x - SLACK and "description" in layout.filled(l) \
                and layout.filled(l) - {"description", "qty", "unit"} and layout.aligned(l) and not DOOR_RE.search(l["text"]):
            # its own description plus another cell, but not a wrap: a row with no quantity
            cur = {"lines": [l], "notes": []}
            rows.append(cur)
            in_note = False
        else:
            notes.append(l["text"])
            cur, in_note = None, False
        prev = l
    comps = []
    for r in rows:
        c = _assemble(layout, r["lines"][0], r["lines"][1:])
        if r["notes"]:
            c["notes"] = " ".join(filter(None, [c.get("notes")] + r["notes"]))
        comps.append(c)
    return comps, notes


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

    def flush(page):
        nonlocal buf
        if cur is not None and buf:
            comps, notes = _resolve(layout, valign, buf)
            for c in comps:
                c["page"] = page
            cur["components"] += comps
            cur["notes"] += notes
            cur["location"].append({"page": page, "bbox": _box([l for _, l in buf])})
        buf = []

    done = False
    for i in pages:
        page = page_lines(pdf.pages[i])
        layout = Layout(calibrate(spec, page))
        kept = []
        for l in page:
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
            if any(p.search(t) for p in skip):
                continue
            if any(p.search(t) for p in end):
                # a book can hold several schedules; end closes the current set, the next header reopens
                flush(i)
                cur = None
                continue
            m = hdr.search(t)
            if m:
                flush(i)
                cur = {"set_number": m.group("num").strip(),
                       "description": (m.groupdict().get("desc") or "").strip() or None,
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
        if done:
            break
    for s in sets:
        text = " ".join([s["description"] or ""] + s["notes"] + s["meta"])
        moved = re.search(r"moved to .*?set\s*(?:HW\s*)?#?\s*([A-Z0-9][\w.-]*)", text, re.I)
        if not s["components"] and moved:
            s["status"], s["moved_to"] = "moved", moved.group(1)
        elif not s["components"] and re.search(r"NOT USED|N/A", text, re.I):
            s["status"] = "not_used"
    return sets


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
                           "components": [], "notes": [], "location": []}
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
                    cur["components"].append({"qty": _qty(get("qty")), "description": desc or None,
                                              "catalog": cat, "mfr": mfr, "finish": get("finish") or None,
                                              "notes": get("notes") or None, "bbox": bbox, "page": i})
                elif get("notes") and cur["components"]:
                    c = cur["components"][-1]
                    c["notes"] = " ".join(filter(None, [c["notes"], get("notes")]))
    return sets


def run(spec, pdf, pages):
    return (run_grid if spec.get("mode") == "grid" else run_columns)(spec, pdf, pages)


if __name__ == "__main__":
    from books import BOOKS, path
    name, spec_file = sys.argv[1], sys.argv[2]
    _, _, a, b = BOOKS[name]
    pdf = pdfplumber.open(path(name))
    spec = json.load(open(spec_file))
    sets = run(spec, pdf, range(a, min(b, len(pdf.pages) - 1) + 1))
    n_notes = sum(len(s["notes"]) for s in sets)
    print(f"{name}: sets={len(sets)} components={sum(len(s['components']) for s in sets)} "
          f"set_notes={n_notes} not_used={sum(1 for s in sets if s.get('status') == 'not_used')}")
    json.dump(sets, open(f"out_{name}.json", "w"), indent=1)
