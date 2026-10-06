"""Door hardware schedule parser: one wide table per page with columns
SET | HARDWARE TYPE | MANUFACTURER - PRODUCT | QTY. | FINISH | NOTES.
The SET cell holds the set number on the first row and the set description
on the rows below; mfr and catalog share the product cell ("IVES - 5BB1")."""
import re

TOL = 3.0

QTY_RE = re.compile(r"^\d+(?:\.0+)?$")
BLANKQ_RE = re.compile(r"^(?:_+|-+|–+|—+)$")
SETNUM_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3})?[A-Z]?$")
NOTUSED_RE = re.compile(r"\bNOT\s+USED\b|^\W*N/?A\W*$", re.I)
MOVED_RE = re.compile(r"\bMOVED\s+TO\b", re.I)
END_RE = re.compile(r"\bEND\s+OF\s+SECTION\b", re.I)
# running footer: "<project> Issue for Bid 122413 - 16" then a date line
FOOT_RE = re.compile(r"\b\d{5,6}\s*-\s*\d{1,3}\s*$")
DATE_RE = re.compile(
    r"\b(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|"
    r"NOVEMBER|DECEMBER)\s+\d{1,2},\s*\d{4}\b", re.I)
# "IVES - 5BB1 4.5" x 4.5"" -> mfr IVES; the mfr part has no digits or slashes
MFR_RE = re.compile(r"^([A-Za-z][A-Za-z&.' ]{0,30}?)\s+-\s+(.+)$")


def _words(line):
    return [w for w in (line.get("words") or []) if str(w.get("text", "")).strip()]


def _header(ws):
    ups = [w["text"].strip().upper().rstrip(".:") for w in ws]
    if "SET" not in ups or "QTY" not in ups or "HARDWARE" not in ups:
        return None
    pos = {}
    for w, u in zip(ws, ups):
        if u == "SET" and "set" not in pos:
            pos["set"] = w["x0"]
        elif u == "HARDWARE" and "type" not in pos:
            pos["type"] = w["x0"]
        elif u in ("MANUFACTURER", "PRODUCT", "MFR") and "prod" not in pos:
            pos["prod"] = w["x0"]
        elif u == "QTY" and "qty" not in pos:
            pos["qty"] = w["x0"]
        elif u == "NOTES" and "notes" not in pos:
            pos["notes"] = w["x0"]
    if "type" not in pos or "prod" not in pos or "qty" not in pos:
        return None
    pos.setdefault("notes", 100000.0)
    return pos


def _zone(w, c):
    x = w["x0"]
    if x < c["type"] - TOL:
        return "set"
    if x < c["prod"] - TOL:
        return "type"
    if x < c["qty"] - 5:
        return "prod"
    if x < c["qty"] + 10:
        t = w["text"].strip()
        # the quantity often sits in the same text run as the product
        if QTY_RE.match(t) or BLANKQ_RE.match(t):
            return "qty"
        return "prod"
    if x < c["notes"] - TOL:
        return "fin"
    return "notes"


def _status(s, text):
    if NOTUSED_RE.search(text):
        s["status"] = "not_used"
        return True
    if MOVED_RE.search(text):
        s["status"] = "moved"
        return True
    return False


def _join(parts):
    s = re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
    return s or None


def parse(pages):
    sets = []
    cur = None
    comp = None
    for pg in pages:
        pno = pg.get("page")
        cols = None
        for ln in pg.get("lines") or []:
            ws = _words(ln)
            if not ws:
                continue
            text = " ".join(w["text"].strip() for w in ws)
            h = _header(ws)
            if h:
                # everything above the column header is the running page header
                cols = h
                continue
            if cols is None:
                continue
            if END_RE.search(text):
                cur = None
                comp = None
                break
            if FOOT_RE.search(text) or DATE_RE.search(text):
                break
            z = {"set": [], "type": [], "prod": [], "qty": [], "fin": [], "notes": []}
            for w in ws:
                z[_zone(w, cols)].append(w["text"].strip())
            setw = z["set"]
            if (setw and SETNUM_RE.match(setw[0])
                    and ("." in setw[0] or z["type"] or z["prod"] or z["qty"] or z["fin"])):
                cur = {"set_number": setw[0], "desc": list(setw[1:]), "status": "active",
                       "first_page": pno, "components": []}
                sets.append(cur)
                comp = None
                _status(cur, " ".join(setw[1:] + z["type"] + z["prod"]))
            elif cur is not None:
                cur["desc"].extend(setw)
            if cur is None:
                continue
            if z["qty"] or z["fin"]:
                q = None
                if z["qty"] and QTY_RE.match(z["qty"][0]):
                    q = int(float(z["qty"][0]))
                comp = {"qty": q, "type": list(z["type"]), "prod": list(z["prod"]),
                        "fin": list(z["fin"]), "page": pno}
                cur["components"].append(comp)
            elif comp is not None and cur["components"] and comp is cur["components"][-1]:
                # wrapped hardware type / product text
                comp["type"].extend(z["type"])
                comp["prod"].extend(z["prod"])
            elif not cur["components"]:
                _status(cur, " ".join(z["type"] + z["prod"]))
    return _out(sets)


def _split_mfr(prod):
    if not prod:
        return None, None
    m = MFR_RE.match(prod)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, prod


def _out(sets):
    res = []
    for s in sets:
        desc = _join(s["desc"])
        if desc and NOTUSED_RE.search(desc):
            s["status"] = "not_used"
        comps = []
        for c in s["components"]:
            mfr, cat = _split_mfr(_join(c["prod"]))
            fin = _join(c["fin"])
            if fin and BLANKQ_RE.match(fin):
                fin = None
            comps.append({
                "qty": c["qty"],
                "description": _join(c["type"]),
                "catalog": cat,
                "finish": fin,
                "mfr": mfr,
                "page": c["page"],
            })
        res.append({
            "set_number": s["set_number"],
            "description": desc,
            "status": s["status"],
            "first_page": s["first_page"],
            "components": comps,
        })
    return res
