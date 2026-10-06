# spec by example: the model labels the structure of the 2 sample pages (which runs form rows, which field
# each run is, which lines are headers); code derives the book's spec from those labels and the interpreter
# runs it over every page. the model never writes a regex or a value.
# usage: python alt_byexample.py   reads alt_struct/dump_out, writes specs_byexample/ and out_byexample/
import json, os, re, collections
import pdfplumber
from spec_parse import run
from e2e import page_texts, expand_pages, D
from alt_induce import induce_grid, shape

FIELDS = ("qty", "description", "catalog", "finish", "mfr")
UNIT = {"EA", "EA.", "EACH", "SET", "SET.", "PR", "PR.", "PAIR", "LOT", "EA-R"}
IDTOK = re.compile(r"^#?[A-Z]{0,4}[-]?\d[\w.\-/]*$")


def generalize(tokens):
    parts = []
    for t in tokens:
        if re.fullmatch(r"\d+", t):
            parts.append(r"\d+")
        else:
            parts.append(re.escape(t) + ("s?" if t[-1:].isalpha() else ""))
    return r"\s*".join(parts)


def derive(pages):
    # pages: list of (labels json, meta dict)
    col_x = collections.defaultdict(list)
    unit_x, header_lines, meta_lines, note_lines = [], [], [], []
    above = total = 0
    for lab, meta in pages:
        by_line = collections.defaultdict(list)
        for rid, r in meta.items():
            by_line[r["line"]].append((int(rid), r))
        assigned = set()
        for s in lab.get("sets", []):
            hr = s.get("set_number_run")
            if hr is not None and str(hr) in meta:
                header_lines.append((meta[str(hr)]["text"], s.get("set_number") or ""))
            first_row_line = None
            for row in s.get("rows", []):
                ids = {fld: [int(i) for i in (row.get(fld) or []) if str(i) in meta] for fld in FIELDS}
                for fld, lst in ids.items():
                    for i in lst:
                        r = meta[str(i)]
                        x0, text = r["x0"], r["text"]
                        assigned.add(i)
                        # a run can hold "1 Ea. Hinge": split the shared run into its columns by character width
                        if fld in ("description", "qty"):
                            cw = (r["x1"] - r["x0"]) / max(len(text), 1)
                            m = re.match(r"^(\d{1,4}(?:\.0+)?|_+|--)\s+", text)
                            if m and fld == "description":
                                col_x["qty"].append(x0); x0 += cw * len(m.group(0)); text = text[m.end():]
                            m = re.match(r"^(EA|Ea|EACH|SET|Set|PR|Pr|PAIR|LOT|EA-R)\.?\s+", text)
                            if m and fld == "description":
                                unit_x.append(x0); x0 += cw * len(m.group(0))
                            if fld == "qty":
                                m2 = re.match(r"^\S+\s+(EA|Ea|EACH|SET|Set|PR|Pr|PAIR|LOT|EA-R)\.?$", text)
                                if m2:
                                    unit_x.append(r["x0"] + cw * (len(text) - len(m2.group(1)) - (1 if text.endswith(".") else 0)))
                        col_x[fld].append(x0)
                lines = sorted({meta[str(i)]["line"] for lst in ids.values() for i in lst})
                if lines:
                    first_row_line = min(first_row_line or lines[0], lines[0])
                    anchor_ids = ids["qty"] or ids["description"]
                    qline = meta[str(anchor_ids[0])]["line"] if anchor_ids else lines[0]
                    total += 1
                    above += any(l < qline for l in lines)
                    # an unassigned run between qty and description on the row's line is the unit
                    for rid, r in by_line[qline]:
                        if rid not in assigned and r["text"].upper().rstrip(".") in {u.rstrip(".") for u in UNIT}:
                            unit_x.append(r["x0"])
            hline = meta[str(hr)]["line"] if hr is not None and str(hr) in meta else None
            if hline is not None and first_row_line is not None:
                for ln in range(hline + 1, first_row_line):
                    txt = " ".join(r["text"] for _, r in sorted(by_line[ln], key=lambda x: x[1]["x0"]))
                    if txt:
                        meta_lines.append(txt)
        for ln, runs in by_line.items():
            if not any(rid in assigned for rid, _ in runs):
                txt = " ".join(r["text"] for _, r in sorted(runs, key=lambda x: x[1]["x0"]))
                if re.match(r"^\s*(NOTES?|Note)\b", txt):
                    note_lines.append(txt)
    if not col_x["description"] or not header_lines:
        return None
    columns = []
    for fld, xs in col_x.items():
        if len(xs) >= 2 or (xs and fld in ("qty", "description")):
            xs.sort()
            columns.append({"field": fld, "x": round(xs[len(xs) // 10] - 2, 1)})
    if unit_x:
        unit_x.sort()
        columns.append({"field": "unit", "x": round(unit_x[len(unit_x) // 10] - 2, 1)})
    if not any(c["field"] == "qty" for c in columns):
        columns.append({"field": "qty", "x": min(c["x"] for c in columns) - 20})
    columns.sort(key=lambda c: c["x"])
    # header: the text before the set number on each labeled header line, generalized
    prefixes, anchored = collections.Counter(), True
    for text, num in header_lines:
        idx = text.find(num) if num else -1
        pre = text[:idx].strip() if idx > 0 else " ".join(t for t in text.split() if not IDTOK.match(t))
        pre = pre.rstrip("#:").strip()
        if not pre:
            continue
        if not text.lower().startswith(pre.lower()):
            anchored = False
        prefixes[re.sub(r"\d+", "#", pre.lower())] = pre
    if not prefixes:
        return None
    alts = [generalize(p.split()) for p in prefixes.values()]
    header = (r"^\s*" if anchored else r"") + "(?:" + "|".join(alts) + r")\s*[#:]?\s*(?P<num>[A-Za-z0-9][\w.\-/]*(?: \d[\w.\-]*)?)[:.]?(?:\s+(?P<desc>.*))?$"
    metas = sorted({r"^\s*" + generalize(t.split()[:2]) for t in meta_lines if len(t.split()) >= 1 and not IDTOK.match(t.split()[0])})
    metas.append(r"^[A-Z]?\d{2,4}[A-Z]?(\s+[A-Z]?\d{2,4}[A-Z]?)*$")
    spec = {"mode": "columns", "set_header": header, "row_start": r"^(\d{1,4}(\.0+)?|_+|-{2})$",
            "columns": columns, "valign": "middle" if total and (above / total > 0.1 or above >= 3) else "top",
            "skip": [r"^\s*(QTY|QUANTITY)\b.*\b(DESCRIPTION|ITEM)\b"], "set_meta": "|".join(metas),
            "end": [r"^\s*END OF SECTION"]}
    if note_lines:
        spec["note_line"] = r"^\s*(NOTES?|Note)\b"
    return spec


def main():
    plan = json.load(open("eval/e2e_plan.json"))
    os.makedirs("specs_byexample", exist_ok=True)
    os.makedirs("out_byexample", exist_ok=True)
    for book, p in plan.items():
        path = D + p["file"]
        pdf = pdfplumber.open(path)
        pages = [i for a, b in p["runs"] for i in range(a, b + 1)]
        spec = induce_grid(pdf, pages)
        if spec is None:
            labeled = []
            for dp in p["dump_pages"]:
                f = f"alt_struct/dump_out/{book}_p{dp}.json"
                if os.path.exists(f):
                    labeled.append((json.load(open(f)), json.load(open(f"alt_struct/dump_input/{book}_p{dp}.meta.json"))))
            spec = derive(labeled) if labeled else None
        if spec is None:
            print(f"{book}: no spec"); json.dump({"sets": []}, open(f"out_byexample/{book}.json", "w")); continue
        # running headers and footers: line shapes that repeat on most schedule pages at one height
        tops = collections.defaultdict(list)
        from lines import page_lines
        H = pdf.pages[pages[0]].height
        hdr_rx = re.compile(spec["set_header"]) if spec.get("set_header") else re.compile(r"$^")
        for i in pages[:12]:
            for l in page_lines(pdf.pages[i]):
                # running headers and footers live in the page margins, and are never set headers
                if 0.12 * H < l["top"] < 0.88 * H or hdr_rx.search(l["text"]):
                    continue
                # a component row that always opens a set sits at one height too, but it is not a running header
                if re.match(r"^(\d{1,4}(\.0+)?|_+|-{2})$", l["words"][0]["text"]):
                    continue
                tops[shape(l["text"])].append(l["top"])
        for sh, ts in tops.items():
            if len(ts) >= max(3, 0.4 * min(len(pages), 12)) and len(sh) > 3 and spec.get("mode") == "columns":
                ts.sort(); med = ts[len(ts) // 2]
                if sum(abs(t - med) < 6 for t in ts) >= 0.8 * len(ts):
                    spec["skip"].append("^" + re.escape(sh).replace("\\#", r"\d+").replace("#", r"\d+") + "$")
        spec_path = f"specs_byexample/{book}.json"
        json.dump(spec, open(spec_path, "w"), indent=1)
        pages2 = expand_pages(spec, page_texts(path), p["runs"])
        sets = run(spec, pdf, pages2)
        json.dump({"spec": spec_path, "pages": pages2, "sets": sets}, open(f"out_byexample/{book}.json", "w"), indent=1)
        cols = [c["field"] for c in spec["columns"]] if spec["mode"] == "columns" else "grid"
        print(f"{book:11s} sets={len(sets):4d} comps={sum(len(s['components']) for s in sets):5d} cols={cols} header={spec.get('set_header', '')[:45]!r}", flush=True)


if __name__ == "__main__":
    main()
