"""Door hardware schedule parser: "Hardware Group/Set #04.1" blocks with rows
qty ("__" when blank) | unit | description | catalog | finish | mfr. There is
no column header and column positions move from page to page, so the column
starts are measured on each page from its own rows."""
import re

TOL = 3.0
GAP = 6.0
SNAP = 2.5
FIELDS = ("desc", "cat", "fin", "mfr")
DEFAULT = {"desc": 125.0, "cat": 242.0, "fin": 472.0, "mfr": 499.0}

QTY_RE = re.compile(r"^\d+(?:\.0+)?$")
BLANKQ_RE = re.compile(r"^(?:_+|-+|–+|—+)$")
UNIT_RE = re.compile(r"^(?:EA|EACH|SETS?|PRS?|PAIRS?|LOT|LF)(?:-[A-Z]+)?\.?$", re.I)
SET_RE = re.compile(
    r"^\s*HARDWARE\s+(?:GROUP\s*/\s*SET|GROUP|SET)\s*(?:NO\.?)?\s*#?\s*"
    r"([A-Z0-9][A-Z0-9.\-]*)\s*[:\-–]?\s*(.*)$", re.I)
NOTUSED_RE = re.compile(r"\bNOT\s+USED\b|^\W*N/?A\W*$", re.I)
MOVED_RE = re.compile(r"\bMOVED\s+TO\b", re.I)
END_RE = re.compile(r"\bEND\s+OF\s+SECTION\b", re.I)
NOTE_RE = re.compile(r"^\s*NOTES?\s*:", re.I)
FOOTER_RES = [
    re.compile(r"\b0?8\s?71\s?00\s*-\s*\d+\s*$"),
    re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$"),
]


def _words(line):
    return [w for w in (line.get("words") or []) if str(w.get("text", "")).strip()]


def _row(ws):
    """(qty, words after qty and unit) when the line opens a component row"""
    if len(ws) < 2 or ws[0]["x0"] > 100:
        return None
    t0 = ws[0]["text"].strip()
    qty = None
    if QTY_RE.match(t0):
        qty = int(float(t0))
        i = 1
    elif BLANKQ_RE.match(t0):
        i = 1
    elif t0.upper() == "AS" and ws[1]["text"].strip().upper().startswith("REQ"):
        i = 2
    else:
        return None
    has_unit = False
    while i < len(ws) and ws[i]["x0"] < 125 and UNIT_RE.match(ws[i]["text"].strip()):
        has_unit = True
        i += 1
    rest = ws[i:]
    if not rest:
        return None
    if not has_unit and rest[0]["x0"] - ws[i - 1]["x1"] < 10:
        # "2 hour label ..." style prose, not a quantity cell
        return None
    return qty, rest


def _runs(ws):
    runs = []
    for w in ws:
        if runs and w["x0"] - runs[-1][-1]["x1"] <= GAP:
            runs[-1].append(w)
        else:
            runs.append([w])
    return runs


def _mode(vals):
    best = None
    bc = -1
    for v in vals:
        c = sum(1 for u in vals if abs(u - v) <= 3)
        if c > bc or (c == bc and v < best):
            best, bc = v, c
    return best


def _page_cols(lines, last):
    descs, cats, fins, mfrs = [], [], [], []
    for ln in lines:
        r = _row(_words(ln))
        if not r:
            continue
        runs = _runs(r[1])
        descs.append(runs[0][0]["x0"])
        if len(runs) >= 2:
            cats.append(runs[1][0]["x0"])
        if len(runs) >= 4:
            a = " ".join(w["text"] for w in runs[-2])
            b = " ".join(w["text"] for w in runs[-1])
            if len(a) <= 8 and len(b) <= 6:
                fins.append(runs[-2][0]["x0"])
                mfrs.append(runs[-1][0]["x0"])
    if not descs:
        return last
    c = dict(last)
    c["desc"] = _mode(descs)
    cats = [x for x in cats if x > c["desc"] + 40]
    if cats:
        c["cat"] = _mode(cats)
    fins = [x for x in fins if x > c["cat"] + 100]
    mfrs = [x for x in mfrs if x > c["cat"] + 100]
    if fins and mfrs:
        c["fin"] = _mode(fins)
        c["mfr"] = _mode(mfrs)
    else:
        shift = c["cat"] - DEFAULT["cat"]
        c["fin"] = DEFAULT["fin"] + shift
        c["mfr"] = DEFAULT["mfr"] + shift
    if c["mfr"] <= c["fin"]:
        c["mfr"] = c["fin"] + 20
    return c


def _col_for(x, cols):
    name = cols[0][0]
    for n, s in cols:
        if x >= s - TOL:
            name = n
    return name


def _assign(words, cols):
    # a new run of words takes the column it starts in; inside a run only an
    # exact column start switches column, so long catalog text stays put
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


def _join(parts):
    s = re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
    return s or None


def parse(pages):
    sets = []
    cur = None
    pc = dict(DEFAULT)
    for pg in pages:
        pno = pg.get("page")
        lines = pg.get("lines") or []
        pc = _page_cols(lines, pc)
        cols = sorted(pc.items(), key=lambda kv: kv[1])
        prev = None
        for ln in lines:
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
            m = SET_RE.match(text)
            if m and re.search(r"\d", m.group(1)):
                num = m.group(1).rstrip(".-")
                rest = m.group(2).strip()
                if not (cur is not None and cur["set_number"] == num):
                    cur = {"set_number": num, "description": None, "status": "active",
                           "first_page": pno, "components": []}
                    sets.append(cur)
                if NOTUSED_RE.search(rest):
                    cur["status"] = "not_used"
                elif MOVED_RE.search(rest):
                    cur["status"] = "moved"
                elif rest:
                    cur["description"] = rest
                prev = None
                continue
            if cur is None:
                continue
            r = _row(ws)
            if r:
                qty, rest = r
                c = {"qty": qty, "page": pno}
                c.update(_assign(rest, cols))
                cur["components"].append(c)
                prev = "comp"
                continue
            if not cur["components"]:
                if NOTUSED_RE.search(text):
                    cur["status"] = "not_used"
                elif MOVED_RE.search(text):
                    cur["status"] = "moved"
            if prev != "comp" or ws[0]["x0"] < pc["desc"] - 6:
                # notes, running headers and footers start at the left margin
                prev = None
                continue
            cells = _assign(ws, cols)
            if cells["desc"] and NOTE_RE.match(" ".join(cells["desc"])):
                prev = None
                continue
            last = cur["components"][-1]
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
