# two-layer alternative with an open source table parser as layer 2:
# layer 1 = our regex page finder, layer 2 = camelot hybrid rows on those pages, column roles from value
# statistics, set boundaries from the deterministic header pattern, wrapped rows merged into the row above
# usage: python alt_camelot.py <camelot_all_pages.json>   writes out_camelot/<book>.json
import json, os, re, sys, collections
import pdfplumber
from lines import page_lines
from alt_induce import FINISH, CODE, UNIT, QTY

tables = json.load(open(sys.argv[1]))
plan = json.load(open("eval/e2e_plan.json"))
D = "../data/"
os.makedirs("out_camelot", exist_ok=True)


def roles_for(rows):
    # rows: list of cell-text lists with equal length
    ncol = max(len(r) for r in rows)
    cols = [[r[j] for r in rows if j < len(r) and r[j]] for j in range(ncol)]
    share = lambda j, rx: sum(bool(rx.match(v.split()[0] if v.split() else "")) for v in cols[j]) / max(len(cols[j]), 1)
    roles = {}
    qty = [j for j in range(ncol) if share(j, QTY) >= 0.5]
    if not qty:
        return None
    roles[qty[0]] = "qty"
    rest = [j for j in range(ncol) if j > qty[0]]
    if rest and sum(v.upper() in UNIT for v in cols[rest[0]]) >= 0.5 * max(len(cols[rest[0]]), 1):
        roles[rest.pop(0)] = "unit"
    if rest:
        roles[rest.pop(0)] = "description"
    fin = max(rest, key=lambda j: share(j, FINISH), default=None)
    if fin is not None and share(fin, FINISH) >= 0.4:
        roles[fin] = "finish"; rest.remove(fin)
    mf = [j for j in rest if share(j, CODE) >= 0.4 and j > max(roles)]
    if mf:
        roles[max(mf)] = "mfr"; rest.remove(max(mf))
    if rest:
        roles[rest[0]] = "catalog"
    return roles


for book, p in plan.items():
    pdf = pdfplumber.open(D + p["file"])
    spec_path = f"specs_induced2/{book}.json"
    hdr = re.compile(json.load(open(spec_path))["set_header"]) if os.path.exists(spec_path) and json.load(open(spec_path)).get("set_header") else None
    pages = [i for a, b in p["runs"] for i in range(a, b + 1)]
    sets, cur = [], None
    for i in pages:
        page = pdf.pages[i]
        H = page.height
        heads = []
        if hdr:
            for l in page_lines(page):
                m = hdr.search(l["text"])
                if m:
                    heads.append((l["top"], m.group("num")))
        rows_all = []
        for t in tables.get(f"{book}_p{i}", []):
            for r in t:
                top = H - max(c["ytop"] for c in r)
                cells = [re.sub(r"\s+", " ", c["text"]).strip() for c in r]
                rows_all.append((top, cells))
        rows_all.sort(key=lambda x: x[0])
        # overlapping tables repeat the same rows: keep one row per height
        dedup, seen_tops = [], []
        for top, cells in rows_all:
            if any(abs(top - t) < 3 for t in seen_tops):
                continue
            seen_tops.append(top)
            text = " ".join(cells)
            # page headers, column headings and set headers are not rows
            if re.search(r"\bQTY\b.*\bDESCRIPTION\b|^\s*(Bulletin|HARDWARE GROUP|Hardware Group)", text) or (hdr and hdr.search(text)):
                continue
            dedup.append((top, cells))
        # a row whose first cell holds no quantity continues the row above
        merged = []
        for top, cells in dedup:
            first = cells[0].strip() if cells else ""
            is_row = bool(first) and bool(QTY.match(first.split()[0]))
            if merged and not is_row and any(c.strip() for c in cells) and top - merged[-1][0] < 40:
                prev = merged[-1][1]
                merged[-1] = (merged[-1][0], [" ".join(filter(None, [a, b])) for a, b in zip(prev, cells + [""] * (len(prev) - len(cells)))])
            else:
                merged.append((top, cells))
        if not merged:
            continue
        roles = roles_for([c for _, c in merged])
        for top, cells in merged:
            # open the set whose header is the last one above this row
            above = [h for h in heads if h[0] <= top]
            if above:
                num = above[-1][1]
                if cur is None or cur["set_number"] != num:
                    cur = {"set_number": num, "status": "active", "location": [{"page": i}], "components": []}
                    sets.append(cur)
            if cur is None or roles is None:
                continue
            if cur["location"][-1]["page"] != i:
                cur["location"].append({"page": i})
            comp = {"qty": None, "description": None, "catalog": None, "finish": None, "mfr": None, "page": i}
            for j, f in roles.items():
                if j < len(cells) and cells[j]:
                    comp[f] = cells[j]
            if not any(comp[k] for k in ("description", "catalog")):
                continue
            q = comp["qty"]
            comp["qty"] = int(float(q)) if q and re.fullmatch(r"\d{1,4}(\.0)?", q) else None
            if comp["qty"] is None and q and not re.fullmatch(r"_+|-{2}|As Req.*", q or ""):
                comp["description"] = " ".join(filter(None, [q, comp["description"]]))
            cur["components"].append(comp)
    json.dump({"sets": sets}, open(f"out_camelot/{book}.json", "w"))
    print(f"{book:11s} sets={len(sets):4d} comps={sum(len(s['components']) for s in sets):5d}", flush=True)
