# deterministic layer 2, second attempt: induce each book's spec from repetition with no LLM
# columns come from where rows align, roles from what the columns hold (as in alt_induce.py),
# and the set header from the line shape that repeats with a distinct id and is followed by rows
# usage: python alt_induce2.py   writes specs_induced2/<book>.json and out_induced2/<book>.json
import json, os, re, sys, collections
import pdfplumber
from lines import page_lines
from spec_parse import run
from e2e import page_texts, expand_pages, D
from alt_induce import QTY, UNIT, FINISH, CODE, runs_of, shape, peaks, induce_grid

KEYWORD = re.compile(r"\b(set|sets|group|groups|hw|heading)\b", re.I)
ROWLIKE = re.compile(r"^(\d{1,4}(\.0)?|_+|-{2})$")
IDTOK = re.compile(r"^#?[A-Z]{0,4}[-]?\d[\w.\-/]*$|^#?[A-Z]{1,3}$")


def columns_from_rows(lines):
    cand = [l for ls in lines.values() for l in ls if QTY.match(l["words"][0]["text"]) and len(l["words"]) >= 3]
    if len(cand) < 5:
        return None, None
    qx = collections.Counter(round(l["words"][0]["x0"]) for l in cand).most_common(1)[0][0]
    rows = [l for l in cand if abs(l["words"][0]["x0"] - qx) <= 6]
    xs = []
    for l in rows:
        xs += {r[0]["x0"] for r in runs_of(l)} | {l["words"][1]["x0"]}
    bands = [b for b in peaks(xs, len(rows), 0.3) if b >= qx - 4]
    if len(bands) < 3:
        return None, rows
    cells = collections.defaultdict(list)
    for l in rows:
        for w in l["words"]:
            k = max(j for j, b in enumerate(bands) if b <= w["x0"] + 4) if w["x0"] + 4 >= bands[0] else 0
            cells[k].append(w["text"])
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
    return [{"field": roles[j], "x": bands[j] - 2} for j in sorted(roles)], rows


def header_pattern(lines, rows, skipped):
    # every line that is not a row is a header candidate at each split "prefix | id" of its first 5 tokens
    row_ids = {id(l) for l in rows}
    groups = collections.defaultdict(list)
    for p, ls in lines.items():
        for i, l in enumerate(ls):
            if id(l) in row_ids or skipped(l) or ROWLIKE.match(l["words"][0]["text"]):
                continue
            toks = l["text"].split()
            for k in range(1, min(8, len(toks))):
                tok = toks[k]
                if not IDTOK.match(tok) or not re.search(r"\d", " ".join(toks[k:k + 2])):
                    continue
                pre = " ".join(toks[:k])
                if not re.search(r"[A-Za-z]{2}", pre):
                    continue
                key = re.sub(r"\d+", "#", pre).lower().rstrip("#:")
                ident = tok if re.search(r"\d", tok) else f"{tok} {toks[k + 1]}" if k + 1 < len(toks) else tok
                followed = any(id(x) in row_ids for x in ls[i + 1:i + 9])
                groups[key].append((ident, followed, pre))
    best = None
    for key, items in groups.items():
        n = len(items)
        distinct = len({i for i, _, _ in items}) / n
        followed = sum(f for _, f, _ in items) / n
        if followed < 0.5 or distinct < 0.5:
            continue
        score = n * distinct * followed * (3 if KEYWORD.search(key) else 1)
        if n == 1 and not KEYWORD.search(key):
            continue
        if best is None or score > best[0]:
            best = (score, key, items[0][2])
    if best is None:
        return None
    pre = best[2]
    parts = []
    for t in pre.split():
        if re.fullmatch(r"\d+", t):
            parts.append(r"\d+")
        else:
            parts.append(re.escape(t) + ("s?" if t[-1:].isalpha() else ""))
    pat = r"\s*".join(parts)
    return r"^\s*" + pat + r"\s*[#:]?\s*(?P<num>[A-Za-z0-9][\w.\-/]*(?: \d[\w.\-]*)?)(?:\s+(?P<desc>.*))?$"


def induce(pdf, pages):
    grid = induce_grid(pdf, pages)
    if grid:
        return grid
    lines = {p: page_lines(pdf.pages[p]) for p in pages}
    # running headers and footers repeat on most pages at the same height; component rows repeat too, but not at one height
    tops = collections.defaultdict(list)
    for ls in lines.values():
        for l in ls:
            if not QTY.match(l["words"][0]["text"]):
                tops[shape(l["text"])].append(l["top"])
    skip = {}
    for sh, ts in tops.items():
        if len(ts) >= max(3, 0.4 * len(pages)) and len(sh) > 3:
            ts.sort()
            med = ts[len(ts) // 2]
            if sum(abs(t - med) < 6 for t in ts) >= 0.8 * len(ts):
                skip[sh] = med
    skipped = lambda l: shape(l["text"]) in skip and abs(l["top"] - skip[shape(l["text"])]) < 6
    columns, rows = columns_from_rows({p: [l for l in ls if not skipped(l)] for p, ls in lines.items()})
    if columns is None:
        return None
    header = header_pattern(lines, rows, skipped)
    if header is None:
        return None
    overlap = total = 0
    rowset = {id(l) for l in rows}
    for ls in lines.values():
        for a, b in zip(ls, ls[1:]):
            if (id(a) in rowset) != (id(b) in rowset):
                total += 1
                overlap += b["top"] < a["bottom"] - 0.5
    valign = "middle" if total and overlap / total > 0.3 else "top"
    skip_re = ["^" + re.escape(s).replace("\\#", r"\d+").replace("#", r"\d+") + "$" for s in skip]
    # column heading rows are made of the field names themselves
    skip_re.append(r"^\s*(QTY|QUANTITY)\b.*\b(DESCRIPTION|ITEM)\b")
    return {"mode": "columns", "set_header": header, "row_start": QTY.pattern, "columns": columns,
            "valign": valign, "skip": skip_re, "note_line": r"^\s*NOTES?\b", "end": [r"^\s*END OF SECTION"]}


def main():
    plan = json.load(open("eval/e2e_plan.json"))
    os.makedirs("specs_induced2", exist_ok=True)
    os.makedirs("out_induced2", exist_ok=True)
    for name, p in plan.items():
        path = D + p["file"]
        pdf = pdfplumber.open(path)
        pages = [i for a, b in p["runs"] for i in range(a, b + 1)]
        spec = induce(pdf, pages)
        if spec is None:
            print(f"{name}: no spec"); json.dump({"sets": []}, open(f"out_induced2/{name}.json", "w")); continue
        spec_path = f"specs_induced2/{name}.json"
        json.dump(spec, open(spec_path, "w"), indent=1)
        pages = expand_pages(spec, page_texts(path), p["runs"])
        sets = run(spec, pdf, pages)
        json.dump({"spec": spec_path, "pages": pages, "sets": sets}, open(f"out_induced2/{name}.json", "w"), indent=1)
        cols = [c["field"] for c in spec["columns"]] if spec["mode"] == "columns" else "grid"
        print(f"{name:11s} sets={len(sets):4d} comps={sum(len(s['components']) for s in sets):5d} cols={cols} header={spec.get('set_header', '')[:50]!r}", flush=True)


if __name__ == "__main__":
    main()
