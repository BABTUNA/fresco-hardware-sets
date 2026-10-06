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

    def is_anchor(self, line):
        first = line["words"][0]
        if self.row.match(first["text"]) and self.field(first["x0"]) == self.fields[0] and len(line["words"]) > 1:
            return True
        f = self.filled(line)
        return self.anchor_field in f and "description" in f and self.aligned(line)

    def straddles(self, line):
        # prose runs straight across column edges; table cells stop short of them
        return any(w["x0"] < c["x"] - SLACK < w["x1"] for w in line["words"] for c in self.cols[1:])

    def aligned(self, line, gap=8):
        ws = line["words"]
        return not self.straddles(line) and any(b["x0"] - a["x1"] > gap for a, b in zip(ws, ws[1:]))


def calibrate(spec, lines, reach=30, share=0.35):
    # the spec fixes column order and roles; each page's own aligned edges fix the positions
    row = re.compile(spec["row_start"])
    cols = sorted(spec["columns"], key=lambda c: c["x"])
    rows = [l for l in lines if row.match(l["words"][0]["text"]) and abs(l["words"][0]["x0"] - cols[0]["x"]) < 15]
    if len(rows) < 3:
        return spec
    hist = collections.Counter()
    for l in rows:
        starts = {l["words"][0]["x0"]} | {b["x0"] for a, b in zip(l["words"], l["words"][1:]) if b["x0"] - a["x1"] > 6}
        hist.update({round(x / 2) * 2 for x in starts})
    peaks = [x for x, c in hist.items() if c >= share * len(rows)]
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
    # "3", "3.0" -> 3; blanks, "__", "As Req" -> None
    return int(float(q)) if q and re.fullmatch(r"\d{1,3}(\.0+)?", q) else None


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
    anchors = [l for k, l in items if k == "anchor"]
    owned = {id(a): [] for a in anchors}
    notes, comp_notes = [], {id(a): [] for a in anchors}
    last = None
    prev = None
    for kind, l in items:
        if kind == "anchor":
            last, prev = l, l
            continue
        if kind == "note":
            (comp_notes[id(last)] if last is not None else notes).append(l["text"])
            continue
        in_body = l["x0"] >= layout.body_x - SLACK
        h = l["bottom"] - l["top"]
        target = None
        if in_body and anchors:
            if valign == "middle":
                mid = (l["top"] + l["bottom"]) / 2
                dist = lambda a: abs((a["top"] + a["bottom"]) / 2 - mid)
                near = sorted(anchors, key=dist)
                best = near[0]
                if len(near) > 1 and dist(near[1]) - dist(best) < 0.6 * h:
                    # tie: the row whose own line left this column empty owns the wrapped text
                    want = layout.filled(l)
                    best = min(near[:2], key=lambda a: (len(want & layout.filled(a)), dist(a)))
                if dist(best) <= 2.6 * h:
                    target = best
            elif last is not None and prev is not None and l["top"] - prev["bottom"] < 1.2 * h:
                target = last
        if target is not None:
            owned[id(target)].append(l)
            prev = l
        else:
            notes.append(l["text"])
            if valign != "middle":
                last = None
    comps = []
    for a in anchors:
        c = _assemble(layout, a, owned[id(a)])
        if comp_notes[id(a)]:
            c["notes"] = " ".join(filter(None, [c.get("notes")] + comp_notes[id(a)]))
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
        for l in page:
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
                continue
            if cur is None:
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
