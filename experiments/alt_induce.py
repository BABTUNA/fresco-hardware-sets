# alternative 3: no llm, induce each book's spec from its own repetition (twix-style)
# then run the same interpreter, so the only difference from our pipeline is who writes the spec
# usage: python alt_induce.py   writes specs_induced/<book>.json and out_induced/<book>.json
import json, os, re, sys, collections
import pdfplumber
from lines import page_lines
from spec_parse import run
from e2e import page_texts, expand_pages, D

QTY = re.compile(r"^(\d{1,4}(\.0)?|_+|-{2}|As)$")
UNIT = {"EA", "EA.", "EACH", "SET", "SET.", "PR", "PR.", "PAIR", "LOT"}
FINISH = re.compile(r"^(6\d\d[A-Z]?|US\d{1,2}[A-Z]?|\d{2}[A-Z]{1,2}|BLK|BK|BLACK|ALM|AL|CLR|MIL|A|AA|DKB|GRY|BSP|SP\d+|\d{3}-\d{3}|---)$", re.I)
CODE = re.compile(r"^([A-Z]{2,5}|[A-Z][a-z]{2,15}|B/O|---)$")


def runs_of(line, gap=6):
    out, cur = [], [line["words"][0]]
    for w in line["words"][1:]:
        if w["x0"] - cur[-1]["x1"] > gap:
            out.append(cur); cur = [w]
        else:
            cur.append(w)
    return out + [cur]


def shape(text):
    return re.sub(r"\d+", "#", text.strip())


def peaks(xs, n, share, merge=6):
    hist = collections.Counter(round(x / 2) * 2 for x in xs)
    out = []
    for x in sorted(x for x, c in hist.items() if c >= share * n):
        if out and x - out[-1] < merge:
            continue
        out.append(x)
    return out


def induce_grid(pdf, pages):
    for p in pages[:4]:
        for t in pdf.pages[p].find_tables():
            rows = t.extract()
            for r in rows[:4]:
                labels = [(c or "").replace("\n", " ").strip().upper() for c in r]
                if "SET" in labels and any("QTY" in l for l in labels):
                    cols = {}
                    for l in labels:
                        if not l or l == "SET":
                            continue
                        if "QTY" in l: cols[l] = "qty"
                        elif "FINISH" in l: cols[l] = "finish"
                        elif "MANUFACTURER" in l or "PRODUCT" in l: cols[l] = "product"
                        elif "NOTE" in l: cols[l] = "notes"
                        elif "CATALOG" in l: cols[l] = "catalog"
                        elif "TYPE" in l or "DESCRIPTION" in l or "ITEM" in l: cols[l] = "description"
                    return {"mode": "grid", "set_column": "SET", "set_number": r"^\d+(\.\d+)?", "columns": cols, "mfr_split": " - "}
    return None


def induce(pdf, pages):
    grid = induce_grid(pdf, pages)
    if grid:
        return grid
    lines = {p: page_lines(pdf.pages[p]) for p in pages}
    # running headers and footers repeat on many pages with only numbers changing
    seen = collections.Counter()
    for ls in lines.values():
        seen.update({shape(l["text"]) for l in ls})
    skip = [s for s, c in seen.items() if c >= max(3, 0.4 * len(pages)) and len(s) > 3]
    skip_re = ["^" + re.escape(s).replace("\\#", r"\d+").replace("#", r"\d+") + "$" for s in skip]
    skipped = lambda l: shape(l["text"]) in skip

    cand = [l for ls in lines.values() for l in ls if not skipped(l) and QTY.match(l["words"][0]["text"]) and len(l["words"]) >= 3]
    if len(cand) < 5:
        return None
    qx = collections.Counter(round(l["words"][0]["x0"]) for l in cand).most_common(1)[0][0]
    rows = [l for l in cand if abs(l["words"][0]["x0"] - qx) <= 6]
    # column starts: every run start, plus the second word, since qty and description often share a run
    xs = []
    for l in rows:
        xs += {r[0]["x0"] for r in runs_of(l)} | {l["words"][1]["x0"]}
    bands = peaks(xs, len(rows), 0.3)
    bands = [b for b in bands if b >= qx - 4]
    if len(bands) < 3:
        return None
    cells = collections.defaultdict(list)
    for l in rows:
        for w in l["words"]:
            k = max(j for j, b in enumerate(bands) if b <= w["x0"] + 4) if w["x0"] + 4 >= bands[0] else 0
            cells[k].append(w["text"])
    # roles from the values each column holds
    roles = {0: "qty"}
    rest = list(range(1, len(bands)))
    if rest and sum(v.upper() in UNIT for v in cells[rest[0]]) >= 0.6 * len(cells[rest[0]]):
        roles[rest.pop(0)] = "unit"
    if rest:
        roles[rest.pop(0)] = "description"
    fin_share = {j: sum(bool(FINISH.match(v)) for v in cells[j]) / max(len(cells[j]), 1) for j in rest}
    code_share = {j: sum(bool(CODE.match(v)) and not FINISH.match(v) for v in cells[j]) / max(len(cells[j]), 1) for j in rest}
    fin = max(rest, key=lambda j: fin_share[j], default=None)
    if fin is not None and fin_share[fin] >= 0.4:
        roles[fin] = "finish"
    else:
        fin = None
    mfr_c = [j for j in rest if j != fin and code_share[j] >= 0.4]
    if mfr_c:
        roles[max(mfr_c)] = "mfr"
    left = [j for j in rest if j not in roles]
    if left:
        roles[left[0]] = "catalog"
        for j in left[1:]:
            roles[j] = "notes"
    columns = [{"field": roles[j], "x": bands[j] - 2} for j in sorted(roles)]

    # set header: a prefix seen about once per block of rows, followed by an id-like token,
    # and sitting above the other header-block lines (door lists, descriptions)
    blocks = []
    for p, ls in lines.items():
        prev_row = False
        for i, l in enumerate(ls):
            is_row = l in rows
            if is_row and not prev_row:
                above = []
                for back in ls[max(0, i - 6):i][::-1]:
                    if back in rows:
                        break
                    if not skipped(back):
                        above.append(back["text"])
                blocks.append(above)
            prev_row = is_row
    ID = re.compile(r"^[#:]?\s*[A-Z]{0,3}-?\d[\w.\-]*$")
    stats = collections.defaultdict(lambda: [0, 0, 0.0])
    for above in blocks:
        hit = {}
        for dist, text in enumerate(above):
            toks = text.split()
            for n in (1, 2, 3, 4):
                if len(toks) <= n:
                    break
                pre = " ".join(toks[:n])
                if not re.search(r"[A-Za-z]", pre) or re.search(r"\d", pre.replace("No.", "")):
                    continue
                nxt = toks[n]
                if pre.endswith("#") or pre.endswith(":"):
                    pass
                hit.setdefault(pre, (dist, bool(ID.match(nxt)) or bool(re.match(r"^#\S+", nxt))))
        for pre, (dist, idlike) in hit.items():
            st = stats[pre]
            st[0] += 1; st[1] += idlike; st[2] += dist
    if not stats:
        return None
    def score(item):
        pre, (n, ids, dist) = item
        return (n * (ids / n), dist / n, len(pre))
    best = max(stats.items(), key=score)[0]
    pat = r"\s*".join(re.escape(t) + ("s?" if t[-1:].isalpha() else "") for t in best.split())
    header = r"^\s*" + pat + r"\s*[#:]?\s*(?P<num>[A-Za-z0-9][\w.\-/]*(?: [0-9][\w.\-]*)?)(?:\s+(?P<desc>.*))?$"

    # wrap style: centered cells make wrapped lines overlap the row line vertically
    overlap = total = 0
    for ls in lines.values():
        for a, b in zip(ls, ls[1:]):
            if (a in rows) != (b in rows):
                total += 1
                overlap += b["top"] < a["bottom"] - 0.5
    valign = "middle" if total and overlap / total > 0.3 else "top"
    return {"mode": "columns", "set_header": header, "row_start": QTY.pattern, "columns": columns,
            "valign": valign, "skip": skip_re, "end": [r"^\s*END OF SECTION"]}


def main():
    plan = json.load(open("eval/e2e_plan.json"))
    os.makedirs("specs_induced", exist_ok=True)
    os.makedirs("out_induced", exist_ok=True)
    for name, p in plan.items():
        path = D + p["file"]
        pdf = pdfplumber.open(path)
        pages = [i for a, b in p["runs"] for i in range(a, b + 1)]
        spec = induce(pdf, pages)
        if spec is None:
            print(f"{name}: no spec induced"); json.dump({"sets": []}, open(f"out_induced/{name}.json", "w")); continue
        spec_path = f"specs_induced/{name}.json"
        json.dump(spec, open(spec_path, "w"), indent=1)
        pages = expand_pages(spec, page_texts(path), p["runs"])
        sets = run(spec, pdf, pages)
        json.dump({"spec": spec_path, "pages": pages, "sets": sets}, open(f"out_induced/{name}.json", "w"), indent=1)
        cols = [c["field"] for c in spec["columns"]] if spec["mode"] == "columns" else "grid"
        print(f"{name:11s} sets={len(sets):4d} comps={sum(len(s['components']) for s in sets):5d} cols={cols} header={spec.get('set_header', '')[:45]!r}", flush=True)


if __name__ == "__main__":
    main()
