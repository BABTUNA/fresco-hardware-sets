"""livelle: "Set: N.0" headers (centered), "Description: ..." line, then rows
with qty, description, catalog, finish and a manufacturer code. "Notes:" prose
sits at the qty x and can continue at the top of the next page. wrapped cells
are attached to the nearest row line (the same generator as centred-cell
schedules), so fragments above or below a row both land on it."""
import re

# layout (left x of each column, pdf points)
QTY_LO, QTY_HI = 70.0, 84.0
UNIT_LO = UNIT_HI = None
CAT_LO = 256.0
FIN_LO = 436.0
MFR_LO = 485.0
LEFT_X = 82.0
LIMIT = 2.6

SET_RE = re.compile(r"^Set\s*:\s*(\S+)\s*(.*)$", re.I)
DESC_RE = re.compile(r"^Description\s*:\s*(.*)$", re.I)


def _header(ws, txt):
    m = SET_RE.match(txt)
    if not m:
        return None
    return m.group(1).rstrip("-:,"), _clean(m.group(2))


# ------------------------------------------------------------------ core
COLS = ("desc", "cat", "fin", "mfr")
NOQTY = {"_", "__", "___", "-", "--", "---", "–", "—"}
QTY_RE = re.compile(r"^\d{1,3}(?:\.\d+)?$")
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
BAND = 5


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
    c = {"qty": None, "desc": [], "cat": [], "fin": [], "mfr": []}
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
    if c["desc"] and c["qty"] is not None:
        u = str(c["desc"][0]["text"]).strip().upper()
        if u in ("EA", "EA.", "EACH"):
            c["desc"].pop(0)
    return c


def _protect(ws, txt):
    if _header(ws, txt) or DESC_RE.match(txt):
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


def _mirror(a, f, frags, h):
    # a centred cell with an odd line count has a twin fragment on the other side of its row line
    t = 2.0 * a["y"] - f["y"]
    for g in frags:
        if g is not f and abs(g["y"] - t) < 0.35 * h and (g["cols"] & f["cols"]):
            return True
    return False


def _choose(f, A, B, frags, h):
    if A is None or B is None:
        return A or B
    da, db = f["y"] - A["y"], B["y"] - f["y"]
    tol = 0.3 * h
    if da + tol < db:
        return A
    if db + tol < da:
        return B
    ma, mb = _mirror(A, f, frags, h), _mirror(B, f, frags, h)
    if mb and not ma:
        return B
    if ma and not mb:
        return A
    fc = f["cols"]
    # an even line count leaves the row line itself empty in that column
    if fc and not (fc & A["cols"]) and (fc & B["cols"]):
        return A
    if fc and not (fc & B["cols"]) and (fc & A["cols"]):
        return B
    return A


def _flush(seg, h):
    anchors = sorted([s for s in seg if s["k"] == "A"], key=lambda s: s["y"])
    frags = [s for s in seg if s["k"] == "F"]
    if not anchors:
        return
    for f in frags:
        A = B = None
        for a in anchors:
            if a["y"] <= f["y"]:
                A = a
            elif B is None:
                B = a
        ch = _choose(f, A, B, frags, h)
        if ch is None or abs(ch["y"] - f["y"]) > LIMIT * h:
            continue
        for k in COLS:
            if f["c"][k]:
                ch["comp"]["pieces"].append((f["y"], k, _t(f["c"][k])))


def _finish(comp):
    cols = {k: [] for k in COLS}
    for _, k, t in sorted(comp["pieces"], key=lambda p: p[0]):
        cols[k].append(t)

    def j(k):
        s = re.sub(r"\s+", " ", " ".join(cols[k])).strip()
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
        seg = []
        seen = False
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
                continue
            if END_RE.search(txt):
                _flush(seg, med_h)
                seg = []
                cur, state = None, None
                continue
            h = _header(ws, txt)
            if h:
                _flush(seg, med_h)
                seg = []
                num, desc = h
                if cur is None or num != cur["set_number"]:
                    cur = {"set_number": num, "description": desc, "first_page": pno,
                           "comps": [], "pre": []}
                    sets.append(cur)
                cur["pre"].append(txt)
                state, seen = "pre", True
                prev = ("header", ln["bottom"])
                continue
            if cur is None:
                continue
            x0 = ws[0]["x0"]
            m = DESC_RE.match(txt)
            if m and x0 < LEFT_X and state == "pre":
                d = _clean(m.group(1))
                if d:
                    cur["description"] = d
                cur["pre"].append(txt)
                seen = True
                prev = ("desc", ln["bottom"])
                continue
            c = _split(ws)
            y = (ln["top"] + ln["bottom"]) / 2.0
            cols = {k for k in COLS if c[k]}
            # a row line carries the single line cells: qty and mfr
            anchor = (c["qty"] is not None
                      or (c["mfr"] and (c["desc"] or c["cat"]) and x0 >= LEFT_X))
            if anchor:
                strong = bool(c["cat"] or c["fin"] or c["mfr"])
                if state == "notes" and not strong:
                    continue
                comp = {"qty": c["qty"], "page": pno, "pieces": []}
                for k in COLS:
                    if c[k]:
                        comp["pieces"].append((y, k, _t(c[k])))
                cur["comps"].append(comp)
                seg.append({"k": "A", "y": y, "comp": comp, "cols": cols})
                state, seen = "table", True
                prev = ("row", ln["bottom"])
                continue
            if x0 < LEFT_X:
                # left margin text: running header at page top, description wrap, or notes
                if not seen:
                    continue
                if (state == "pre" and prev is not None and prev[0] in ("desc", "dwrap")
                        and cur["description"] and ln["top"] - prev[1] <= gap_max):
                    cur["description"] = cur["description"] + " " + txt
                    prev = ("dwrap", ln["bottom"])
                    continue
                if state == "pre":
                    cur["pre"].append(txt)
                _flush(seg, med_h)
                seg = []
                state = "notes"
                prev = ("note", ln["bottom"])
                continue
            seen = True
            prev = ("frag", ln["bottom"])
            if state == "notes":
                continue
            dtx = _t(c["desc"])
            if dtx and NOTE_RE.match(dtx):
                _flush(seg, med_h)
                seg = []
                state = "notes"
                continue
            if state == "pre":
                cur["pre"].append(txt)
            seg.append({"k": "F", "y": y, "c": c, "cols": cols})
        _flush(seg, med_h)
    out = []
    for s in sets:
        out.append({"set_number": s["set_number"], "description": s["description"],
                    "status": _status(s), "first_page": s["first_page"],
                    "components": [_finish(c) for c in s["comps"]]})
    return out
