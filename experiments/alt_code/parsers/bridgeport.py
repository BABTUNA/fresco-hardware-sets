"""bridgeport: "Heading #N" headers, then "Item #" door lines and opening size /
remark lines in the description column. rows: qty, description, catalog,
finish, no manufacturer column. catalog cells wrap onto lines holding only
catalog text; trailing remarks sit in the description column as prose."""
import re

# layout (left x of each column, pdf points)
QTY_LO, QTY_HI = 98.0, 126.0
UNIT_LO = UNIT_HI = None
DESC_LO = 126.0
CAT_LO = 236.0
FIN_LO = 510.0
MFR_LO = None
LEFT_X = 98.0
LEFT_NOTES = False
QTYCOL_NOTES = True
DESC_FREE_CONT = False
QTYLESS_ROWS = True
DOORS_BLOCK = False
STRICT_ROWS = False
DESC_WRAP = False
LEGEND_RE = None

SET_RE = re.compile(r"^Heading\s*#\s*(\S+)\s*(.*)$", re.I)
ITEM_RE = re.compile(r"^Item\s*#", re.I)


def _header(ws, txt):
    m = SET_RE.match(txt)
    if not m:
        return None
    return m.group(1).rstrip("-:,"), _clean(m.group(2))


def _marker(ws, txt):
    if ITEM_RE.match(txt):
        return "pre"
    return None


# ------------------------------------------------------------------ core
COLS = ("desc", "cat", "fin", "mfr")
UNITS = {"EA", "EA.", "EACH", "SET", "SETS", "PR", "PR.", "PAIR", "PRS"}
NOQTY = {"_", "__", "___", "-", "--", "---", "–", "—"}
QTY_RE = re.compile(r"^\d{1,3}(?:\.\d+)?$")
WEAK_QTY = re.compile(r"^\d+\.0+$")
NOTE_RE = re.compile(r"^NOTES?\b", re.I)
END_RE = re.compile(r"\bEND\s+OF\s+SECTION\b", re.I)
CONT_RE = re.compile(r"^\(?\s*cont(?:inued|'d|d)?\.?\s*\)?$", re.I)
FOOTER_RES = (
    re.compile(r"\bPage\s+\d+\s+of\s+\d+\s*$", re.I),
    re.compile(r"\b0?8\s?71\s?00\s*-\s*\d+\s*$"),
    re.compile(r"^(?:SECTION\s+)?0?8\s?71\s?00\b", re.I),
    re.compile(r"^DOOR\s+HARDWARE\b", re.I),
    re.compile(r"^Copyright\b", re.I),
)
START_CONN = re.compile(
    r"^(?:[-,/&+)\]]|(?:IN|AS|TO|OF|FROM|WITH|AND|OR|FOR|AT|ON|PER|THE|INTO)\b)", re.I)
END_CONN = re.compile(
    r"(?:[-,/&+(\[]|\b(?:IN|AS|TO|OF|FROM|WITH|AND|OR|FOR|BY|AT|ON|PER|THE|INTO))$", re.I)
BAND = 5
FIT_MARGIN = 8.0
SPAN_GAP = 5.0


def _ws(line):
    ws = [w for w in (line.get("words") or []) if str(w.get("text", "")).strip()]
    ws.sort(key=lambda w: w["x0"])
    return ws


def _t(ws):
    return " ".join(str(w["text"]).strip() for w in ws).strip()


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", s)).strip().lower()


def _clean(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    s = re.sub(r"^[-–—:]+\s*", "", s).strip()
    if not s or CONT_RE.match(s):
        return None
    return s


def _is_footer(txt):
    return any(r.search(txt) for r in FOOTER_RES)


def _qty_val(tok):
    if tok and re.match(r"^\d+(?:\.\d+)?$", tok):
        return int(float(tok))
    return None


def _split(ws):
    c = {"qty": None, "unit": False, "desc": [], "cat": [], "fin": [], "mfr": []}
    rest = list(ws)
    if rest and QTY_LO <= rest[0]["x0"] < QTY_HI:
        t0 = str(rest[0]["text"]).strip()
        if QTY_RE.match(t0) or t0 in NOQTY:
            c["qty"] = t0
            rest = rest[1:]
        elif (t0.lower() == "as" and len(rest) > 1
              and str(rest[1]["text"]).strip().lower().startswith("req")):
            c["qty"] = ""
            rest = rest[2:]
    for w in rest:
        x = w["x0"]
        if MFR_LO is not None and x >= MFR_LO:
            c["mfr"].append(w)
        elif FIN_LO is not None and x >= FIN_LO:
            c["fin"].append(w)
        elif x >= CAT_LO:
            c["cat"].append(w)
        else:
            c["desc"].append(w)
    if c["desc"]:
        w = c["desc"][0]
        u = str(w["text"]).strip().upper()
        if UNIT_LO is not None:
            if UNIT_LO <= w["x0"] < UNIT_HI and u in UNITS:
                c["desc"].pop(0)
                c["unit"] = True
        elif c["qty"] is not None and u in ("EA", "EA.", "EACH"):
            c["desc"].pop(0)
            c["unit"] = True
    return c


def _protect(ws, txt):
    if _header(ws, txt) or _marker(ws, txt):
        return True
    w = ws[0]
    return QTY_LO <= w["x0"] < QTY_HI and bool(QTY_RE.match(str(w["text"]).strip()))


def _running_keys(pages):
    # text repeated in the top / bottom band of many pages is a running header or footer
    n = len(pages)
    if n < 2:
        return set()
    cnt = {}
    for pg in pages:
        ls = pg.get("lines") or []
        seen = set()
        for i, ln in enumerate(ls):
            if BAND <= i < len(ls) - BAND:
                continue
            ws = _ws(ln)
            if not ws:
                continue
            txt = _t(ws)
            if _protect(ws, txt):
                continue
            seen.add(_norm(txt))
        for k in seen:
            cnt[k] = cnt.get(k, 0) + 1
    need = max(2, -(-3 * n // 10))
    return {k for k, v in cnt.items() if k and v >= need}


def _spans(ws):
    # prose runs straight across a column boundary, table cells start after a gap
    for a, b in zip(ws, ws[1:]):
        for lim in (CAT_LO, FIN_LO, MFR_LO):
            if lim is not None and a["x0"] < lim <= b["x0"] and b["x0"] - a["x1"] < SPAN_GAP:
                return True
    return False


def _new_comp(c, pno, ln):
    comp = {"qty": c["qty"], "page": pno, "cols": {k: [] for k in COLS},
            "lastx": {}, "bottom": ln["bottom"]}
    _append(comp, c, ln)
    return comp


def _append(comp, c, ln):
    comp["lastx"] = {}
    for k in COLS:
        if c[k]:
            comp["cols"][k].append(_t(c[k]))
            comp["lastx"][k] = c[k][-1]["x1"]
    comp["bottom"] = ln["bottom"]


def _fits(comp, c, k, limit):
    # true when the first word could not have fit on the previous line of that cell
    px = comp["lastx"].get(k)
    if px is None or limit is None or not c[k]:
        return False
    w = c[k][0]
    return px + 2.5 + (w["x1"] - w["x0"]) > limit - FIT_MARGIN


def _looks_cont(comp, c):
    for k in ("desc", "cat"):
        if c[k]:
            t = _t(c[k])
            if t[:1].islower() or START_CONN.match(t):
                return True
            if comp["cols"][k] and END_CONN.search(comp["cols"][k][-1]):
                return True
    nxt = FIN_LO if FIN_LO is not None else MFR_LO
    return _fits(comp, c, "desc", CAT_LO) or _fits(comp, c, "cat", nxt)


def _finish(comp):
    def j(k):
        s = re.sub(r"\s+", " ", " ".join(comp["cols"][k])).strip()
        return s or None
    return {"qty": _qty_val(comp["qty"]), "description": j("desc"), "catalog": j("cat"),
            "finish": j("fin"), "mfr": j("mfr"), "page": comp["page"]}


def _status(s):
    blob = " ".join(s["pre"] + [s["description"] or ""])
    if re.search(r"\bNOT\s+USED\b|\bNOT\s+IN\s+USE\b|\bUNUSED\b", blob, re.I):
        return "not_used"
    if re.search(r"\bMOVED\b", blob, re.I):
        return "moved"
    if not s["comps"] and re.search(r"\bN/A\b|\bDELETED\b|\bVOID\b|\bOMITTED\b", blob, re.I):
        return "not_used"
    return "active"


def parse(pages):
    keys = _running_keys(pages)
    sets = []
    cur = None
    state = None
    for pg in pages:
        pno = pg.get("page")
        lines = pg.get("lines") or []
        hs = sorted(l["bottom"] - l["top"] for l in lines if l["bottom"] > l["top"])
        med_h = hs[len(hs) // 2] if hs else 10.0
        gap_max = max(4.0, 1.1 * med_h)
        comp = None
        prev = None
        n = len(lines)
        for i, ln in enumerate(lines):
            ws = _ws(ln)
            if not ws:
                continue
            txt = _t(ws)
            if (i < BAND or i >= n - BAND) and _norm(txt) in keys and not _protect(ws, txt):
                continue
            if _is_footer(txt):
                comp = None
                continue
            if END_RE.search(txt) or (LEGEND_RE is not None and LEGEND_RE.search(txt)):
                cur, state, comp = None, None, None
                continue
            h = _header(ws, txt)
            if h:
                num, desc = h
                if cur is None or num != cur["set_number"]:
                    cur = {"set_number": num, "description": desc, "first_page": pno,
                           "comps": [], "pre": []}
                    sets.append(cur)
                elif desc and not cur["description"]:
                    cur["description"] = desc
                cur["pre"].append(txt)
                state, comp = "pre", None
                prev = ("header", ln["bottom"])
                continue
            if cur is None:
                continue
            mk = _marker(ws, txt)
            if mk:
                if mk == "doors":
                    state = "doors"
                elif mk == "table":
                    state = "table"
                if state != "table":
                    cur["pre"].append(txt)
                comp = None
                prev = ("marker", ln["bottom"])
                continue
            c = _split(ws)
            x0 = ws[0]["x0"]
            if c["qty"] is not None and (c["desc"] or c["cat"] or c["fin"] or c["mfr"]):
                strong = bool(c["cat"] or c["fin"] or c["mfr"])
                ok = True
                if DOORS_BLOCK and state in ("pre", "doors") and not c["unit"]:
                    ok = False
                if STRICT_ROWS and not strong and not (c["unit"] or WEAK_QTY.match(c["qty"])):
                    ok = False
                if state == "notes" and not (strong or c["unit"]):
                    ok = False
                if ok:
                    comp = _new_comp(c, pno, ln)
                    cur["comps"].append(comp)
                    state = "table"
                    prev = ("row", ln["bottom"])
                    continue
            if state in ("pre", "doors"):
                if (DESC_WRAP and state == "pre" and prev is not None
                        and prev[0] in ("header", "dwrap") and cur["description"]
                        and x0 < LEFT_X + 2 and ln["top"] - prev[1] <= gap_max):
                    cur["description"] = cur["description"] + " " + txt
                    prev = ("dwrap", ln["bottom"])
                    continue
                cur["pre"].append(txt)
                prev = ("pre", ln["bottom"])
                continue
            prev = ("other", ln["bottom"])
            if c["qty"] is not None:
                comp = None
                continue
            if x0 < LEFT_X:
                comp = None
                if LEFT_NOTES:
                    state = "notes"
                continue
            if x0 < DESC_LO:
                comp = None
                if QTYCOL_NOTES:
                    state = "notes"
                continue
            dtx = _t(c["desc"])
            if dtx and NOTE_RE.match(dtx):
                comp, state = None, "notes"
                continue
            if c["desc"] and _spans(ws):
                comp, state = None, "notes"
                continue
            near = (comp is not None and state == "table" and comp["page"] == pno
                    and ln["top"] - comp["bottom"] <= gap_max)
            if not near:
                if QTYLESS_ROWS and state == "table" and c["desc"] and (c["cat"] or c["mfr"]):
                    comp = _new_comp(c, pno, ln)
                    cur["comps"].append(comp)
                elif c["desc"] and not DESC_FREE_CONT and state == "table":
                    comp, state = None, "notes"
                continue
            if not c["desc"]:
                _append(comp, c, ln)
                continue
            if c["cat"] or c["fin"] or c["mfr"]:
                if QTYLESS_ROWS and not _looks_cont(comp, c):
                    comp = _new_comp(c, pno, ln)
                    cur["comps"].append(comp)
                else:
                    _append(comp, c, ln)
                continue
            if txt.endswith(":"):
                comp, state = None, "notes"
                continue
            if DESC_FREE_CONT or _looks_cont(comp, c):
                _append(comp, c, ln)
            else:
                comp, state = None, "notes"
    out = []
    for s in sets:
        out.append({"set_number": s["set_number"], "description": s["description"],
                    "status": _status(s), "first_page": s["first_page"],
                    "components": [_finish(c) for c in s["comps"]]})
    return out
