"""Door hardware schedule parser: "HW 12A <description>" blocks, then
"Each Opening to Receive:" and a Quantity | Description | Model Number |
Finish | Manf grid where quantity and unit share the first cell ("1 Ea.")."""
import re

QTY_X = 64.0
DEFAULT_COLS = [("desc", 119.0), ("cat", 316.0), ("fin", 521.0), ("mfr", 563.0)]

TOL = 3.0
GAP = 6.0
SNAP = 2.5
FIELDS = ("desc", "cat", "fin", "mfr")

QTY_RE = re.compile(r"^\d+(?:\.0+)?$")
BLANKQ_RE = re.compile(r"^(?:_+|-+|–+|—+)$")
UNIT_RE = re.compile(r"^(?:EA|EACH|SETS?|PRS?|PAIRS?|LOT|LF)(?:-[A-Z]+)?\.?$", re.I)
HW_RE = re.compile(r"^\s*HW\s*#?\s*-?\s*([A-Z]{0,3}\d+[A-Z0-9.\-]*)\s*(.*)$", re.I)
NOTUSED_RE = re.compile(r"\bNOT\s+USED\b|^\W*N/?A\W*$", re.I)
MOVED_RE = re.compile(r"\bMOVED\s+TO\b", re.I)
END_RE = re.compile(r"\bEND\s+OF\s+SECTION\b", re.I)
EACH_RE = re.compile(r"^\s*EACH\s+OPENING\b", re.I)
NOTE_RE = re.compile(r"^\s*NOTES?\s*:", re.I)
FOOTER_RES = [
    re.compile(r"\b0?8\s?71\s?00\s*-\s*\d+\s*$"),
    re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$"),
]
HEAD_KEYS = {
    "DESCRIPTION": "desc",
    "MODEL": "cat",
    "CATALOG": "cat",
    "FINISH": "fin",
    "MANF": "mfr",
    "MFR": "mfr",
    "MFG": "mfr",
    "MANUFACTURER": "mfr",
}


def _words(line):
    return [w for w in (line.get("words") or []) if str(w.get("text", "")).strip()]


def _col_for(x, cols):
    name = cols[0][0]
    for n, s in cols:
        if x >= s - TOL:
            name = n
    return name


def _assign(words, cols):
    # a new run of words takes the column it starts in; inside a run only an
    # exact column start switches column
    out = {f: [] for f in FIELDS}
    starts = dict(cols)
    order = {n: i for i, (n, _) in enumerate(cols)}
    cur = None
    prev = None
    for w in words:
        here = _col_for(w["x0"], cols)
        if cur is None or prev is None or w["x0"] - prev["x1"] > GAP:
            cur = here
        elif order[here] > order[cur] and abs(w["x0"] - starts[here]) <= SNAP:
            cur = here
        out[cur].append(w["text"].strip())
        prev = w
    return out


def _is_colhead(ws):
    ups = {w["text"].strip().upper().rstrip(".:") for w in ws}
    return ("QTY" in ups or "QUANTITY" in ups) and "DESCRIPTION" in ups


def _cols_from_header(ws, cols, qty_x):
    starts = dict(cols)
    for w in ws:
        u = w["text"].strip().upper().rstrip(".:")
        if u in ("QTY", "QUANTITY"):
            qty_x = w["x0"]
        elif u in HEAD_KEYS and HEAD_KEYS[u] in starts:
            starts[HEAD_KEYS[u]] = w["x0"]
    return sorted(starts.items(), key=lambda kv: kv[1]), qty_x


def _lead(lead, qty_x):
    toks = [w["text"].strip() for w in lead]
    qty = None
    hasq = False
    i = 0
    if lead[0]["x0"] >= qty_x - 7 and QTY_RE.match(toks[0]):
        qty = int(float(toks[0]))
        hasq = True
        i = 1
    elif lead[0]["x0"] >= qty_x - 7 and BLANKQ_RE.match(toks[0]):
        hasq = True
        i = 1
    elif len(toks) > 1 and toks[0].upper() == "AS" and toks[1].upper().startswith("REQ"):
        hasq = True
        i = 2
    has_unit = False
    for t in toks[i:]:
        if UNIT_RE.match(t):
            has_unit = True
        else:
            return None, False, False
    if not (hasq or has_unit):
        return None, False, False
    return qty, True, has_unit


def _new_comp(qty, cells, page):
    c = {"qty": qty, "page": page}
    for f in FIELDS:
        c[f] = list(cells.get(f) or [])
    return c


def _join(parts):
    s = re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
    return s or None


def parse(pages):
    sets = []
    cur = None
    cols = list(DEFAULT_COLS)
    qty_x = QTY_X
    in_head = False
    for pg in pages:
        pno = pg.get("page")
        prev = None
        for ln in pg.get("lines") or []:
            ws = _words(ln)
            if not ws:
                continue
            text = " ".join(w["text"].strip() for w in ws)
            if any(r.search(text) for r in FOOTER_RES):
                prev = None
                continue
            if END_RE.search(text):
                cur = None
                prev = None
                continue
            desc_x = cols[0][1]
            m = HW_RE.match(text)
            if m and ws[0]["x0"] < desc_x - TOL:
                num = m.group(1)
                d = m.group(2).strip()
                notused = bool(NOTUSED_RE.search(d))
                moved = bool(MOVED_RE.search(d))
                if cur is not None and cur["set_number"] == num:
                    # same set printed twice in a row (revision); keep one entry
                    if not notused and not moved:
                        cur["status"] = "active"
                        cur["description"] = d or cur["description"]
                else:
                    cur = {"set_number": num, "description": None, "status": "active",
                           "first_page": pno, "components": []}
                    sets.append(cur)
                    if notused:
                        cur["status"] = "not_used"
                    elif moved:
                        cur["status"] = "moved"
                    else:
                        cur["description"] = d or None
                in_head = True
                prev = None
                continue
            if cur is None:
                continue
            if _is_colhead(ws):
                cols, qty_x = _cols_from_header(ws, cols, qty_x)
                in_head = False
                prev = None
                continue
            if EACH_RE.match(text):
                in_head = False
                prev = None
                continue
            desc_x = cols[0][1]
            lead = [w for w in ws if w["x0"] < desc_x - TOL]
            body = [w for w in ws if w["x0"] >= desc_x - TOL]
            if lead:
                qty, ok, has_unit = _lead(lead, qty_x)
                if not ok or not body:
                    # notes, running headers and footers
                    if not cur["components"]:
                        if NOTUSED_RE.search(text):
                            cur["status"] = "not_used"
                        elif MOVED_RE.search(text):
                            cur["status"] = "moved"
                    prev = None
                    continue
                cur["components"].append(_new_comp(qty, _assign(body, cols), pno))
                in_head = False
                prev = "comp"
                continue
            if in_head and not cur["components"]:
                # wrapped set description
                if cur["description"]:
                    cur["description"] += " " + text
                elif cur["status"] == "active":
                    cur["description"] = text
                continue
            if prev != "comp" or not cur["components"]:
                continue
            cells = _assign(body, cols)
            if cells["desc"] and NOTE_RE.match(" ".join(cells["desc"])):
                prev = None
                continue
            last = cur["components"][-1]
            if cells["desc"] and cells["mfr"] and last["mfr"]:
                cur["components"].append(_new_comp(None, cells, pno))
                continue
            for f in FIELDS:
                last[f].extend(cells[f])
    return _out(sets)


def _out(sets):
    res = []
    for s in sets:
        comps = []
        for c in s["components"]:
            fin = _join(c["fin"])
            mfr = _join(c["mfr"])
            if fin and BLANKQ_RE.match(fin):
                fin = None
            if mfr and BLANKQ_RE.match(mfr):
                mfr = None
            comps.append({
                "qty": c["qty"],
                "description": _join(c["desc"]),
                "catalog": _join(c["cat"]),
                "finish": fin,
                "mfr": mfr,
                "page": c["page"],
            })
        res.append({
            "set_number": s["set_number"],
            "description": s["description"],
            "status": s["status"],
            "first_page": s["first_page"],
            "components": comps,
        })
    return res
