"""Door hardware schedule parser: "Hardware Group No. X" blocks with a
QTY | unit | DESCRIPTION | CATALOG NUMBER | FINISH | MFR grid."""
import re

# column starts (PDF points) seen in the sample; a QTY/DESCRIPTION header row overrides them
QTY_X = 80.0
DEFAULT_COLS = [("desc", 143.0), ("cat", 275.0), ("fin", 470.0), ("mfr", 511.0)]
USE_HEADER = True

TOL = 3.0
GAP = 6.0
SNAP = 2.5
FIELDS = ("desc", "cat", "fin", "mfr")

QTY_RE = re.compile(r"^\d+(?:\.0+)?$")
BLANKQ_RE = re.compile(r"^(?:_+|-+|–+|—+)$")
UNIT_RE = re.compile(r"^(?:EA|EACH|SETS?|PRS?|PAIRS?|LOT|LF)(?:-[A-Z]+)?\.?$", re.I)
GROUP_RE = re.compile(r"^\s*HARDWARE\s+GROUP\s+NO\.?\s*:?\s*([A-Z0-9][A-Z0-9.\-]*)(.*)$", re.I)
NOTUSED_RE = re.compile(r"\bNOT\s+USED\b|^\W*N/?A\W*$", re.I)
MOVED_RE = re.compile(r"\bMOVED\s+TO\b", re.I)
END_RE = re.compile(r"\bEND\s+OF\s+SECTION\b", re.I)
PROVIDE_RE = re.compile(r"^\s*PROVIDE\s+EACH\b", re.I)
NOTE_RE = re.compile(r"^\s*NOTES?\s*:", re.I)
# a free text item (no unit, no description) only wraps when its line ends mid phrase
CONNECT_RE = re.compile(r"^(?:BY|WITH|AND|OR|OF|TO|FOR|AT|IN|ON|THE|A|&|-|/)$|[,/&-]$", re.I)
FOOTER_RES = [
    re.compile(r"\b0?8\s?71\s?00\s*-\s*\d+\s*$"),
    re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$"),
]
HEAD_KEYS = {
    "DESCRIPTION": "desc",
    "CATALOG": "cat",
    "MODEL": "cat",
    "FINISH": "fin",
    "MFR": "mfr",
    "MFG": "mfr",
    "MANF": "mfr",
    "MANUFACTURER": "mfr",
}


def _words(line):
    return [w for w in (line.get("words") or []) if str(w.get("text", "")).strip()]


def _core(text):
    # some books prefix every paragraph with an auto number like "PART 53 -"
    return re.sub(r"^\s*PART\s+\d+\s*-\s*", "", text)


def _col_for(x, cols):
    name = cols[0][0]
    for n, s in cols:
        if x >= s - TOL:
            name = n
    return name


def _assign(words, cols):
    # a new run of words takes the column it starts in; inside a run only an
    # exact column start switches column, so long wrapped text stays in its cell
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


def _status(s, text):
    if NOTUSED_RE.search(text):
        s["status"] = "not_used"
        return True
    if MOVED_RE.search(text):
        s["status"] = "moved"
        return True
    return False


def _lead(lead, qty_x):
    # words left of the description column: quantity and unit only
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


def _new_comp(qty, cells, page, loose=False):
    c = {"qty": qty, "page": page, "loose": loose, "tail": ""}
    for f in FIELDS:
        c[f] = list(cells.get(f) or [])
    c["tail"] = _tail(cells)
    return c


def _tail(cells):
    words = []
    for f in FIELDS:
        words.extend(cells.get(f) or [])
    return words[-1] if words else ""


def _join(parts):
    s = re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
    return s or None


def _set_desc(rest):
    d = rest.strip(" :-–—\t")
    if not d or d.startswith("(") or NOTUSED_RE.search(d) or MOVED_RE.search(d):
        return None
    return d


def parse(pages):
    sets = []
    cur = None
    cols = list(DEFAULT_COLS)
    qty_x = QTY_X
    awaiting = False
    for pg in pages:
        pno = pg.get("page")
        prev = None
        for ln in pg.get("lines") or []:
            ws = _words(ln)
            if not ws:
                continue
            text = " ".join(w["text"].strip() for w in ws)
            core = _core(text)
            if any(r.search(text) for r in FOOTER_RES):
                prev = None
                continue
            if END_RE.search(text):
                cur = None
                prev = None
                continue
            m = GROUP_RE.match(core)
            if m:
                num = m.group(1).rstrip(".-")
                rest = m.group(2)
                if cur is not None and cur["set_number"] == num:
                    # the same header printed again; keep one entry
                    cur["status"] = "active"
                else:
                    cur = {"set_number": num, "description": None, "status": "active",
                           "first_page": pno, "components": []}
                    sets.append(cur)
                d = _set_desc(rest)
                if d:
                    cur["description"] = d
                _status(cur, rest)
                awaiting = True
                prev = None
                continue
            if _is_colhead(ws):
                if USE_HEADER:
                    cols, qty_x = _cols_from_header(ws, cols, qty_x)
                awaiting = False
                prev = None
                continue
            if cur is None:
                continue
            if PROVIDE_RE.match(core):
                awaiting = False
                prev = None
                continue
            if not cur["components"] and _status(cur, core):
                prev = None
                continue
            desc_x = cols[0][1]
            lead = [w for w in ws if w["x0"] < desc_x - TOL]
            body = [w for w in ws if w["x0"] >= desc_x - TOL]
            if lead:
                qty, ok, has_unit = _lead(lead, qty_x)
                if not ok:
                    # notes, door lists, page headers
                    prev = None
                    continue
                if not has_unit and (awaiting or not body):
                    prev = None
                    continue
                cells = _assign(body, cols)
                loose = not has_unit and not cells["desc"]
                cur["components"].append(_new_comp(qty, cells, pno, loose))
                awaiting = False
                prev = "comp"
                continue
            if prev != "comp" or not cur["components"]:
                continue
            cells = _assign(body, cols)
            if cells["desc"] and NOTE_RE.match(" ".join(cells["desc"])):
                prev = None
                continue
            last = cur["components"][-1]
            if last["loose"] and not CONNECT_RE.search(last["tail"]):
                prev = None
                continue
            if cells["desc"] and cells["mfr"] and last["mfr"]:
                # a line item printed without a quantity
                cur["components"].append(_new_comp(None, cells, pno))
                continue
            for f in FIELDS:
                last[f].extend(cells[f])
            last["tail"] = _tail(cells) or last["tail"]
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
