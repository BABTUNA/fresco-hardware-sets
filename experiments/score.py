# score extractor output against image-labeled ground truth, page by page
# usage: python score.py <spec prefix>   e.g. "oneshot_" runs specs/oneshot_<book>.json
import json, os, re, sys, glob, difflib, collections
import pdfplumber
from books import BOOKS, path
from spec_parse import run

FIELDS = ["qty", "description", "catalog", "finish", "mfr"]


def norm(v):
    if v is None:
        return None
    v = re.sub(r"\s+", " ", str(v)).strip().upper()
    v = v.replace("–", "-").replace("”", '"').replace("“", '"').replace("’", "'").replace("″", '"').replace("′", "'")
    # labelers disagree on whether a hyphen at a line break keeps the space after it
    v = re.sub(r"(?<=\w)- (?=\w)", "-", v)
    return v or None


def norm_set(v):
    return re.sub(r"^0+(?=\d)", "", re.sub(r"\s+", " ", str(v)).strip().upper())


def sim(a, b):
    key = lambda c: f"{norm(c.get('description')) or ''} | {norm(c.get('catalog')) or ''}"
    return difflib.SequenceMatcher(None, key(a), key(b)).ratio()


def align(gt, ours, floor=0.5):
    # order-preserving alignment (both lists follow page order)
    n, m = len(gt), len(ours)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            s = sim(gt[i], ours[j])
            take = best[i + 1][j + 1] + s if s >= floor else -1
            best[i][j] = max(take, best[i + 1][j], best[i][j + 1])
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        s = sim(gt[i], ours[j])
        if s >= floor and best[i][j] == best[i + 1][j + 1] + s:
            pairs.append((gt[i], ours[j])); i += 1; j += 1
        elif best[i][j] == best[i + 1][j]:
            i += 1
        else:
            j += 1
    return pairs


def main(prefix):
    plan = json.load(open("eval/plan.json"))
    tot = collections.Counter()
    rows = []
    for name, p in plan.items():
        spec_file = f"specs/{prefix}{name}.json"
        if not os.path.exists(spec_file):
            continue
        pdf = pdfplumber.open(path(name))
        lo, hi = p["range"]
        try:
            sets = run(json.load(open(spec_file)), pdf, range(lo, hi + 1))
        except Exception as e:
            print(f"{name}: spec crashed: {e!r}")
            continue
        b = collections.Counter()
        for gt_file in sorted(glob.glob(f"eval/gt/{name}_p*.json")):
            page = int(re.search(r"_p(\d+)\.json$", gt_file).group(1))
            gt = json.load(open(gt_file))
            ours_by_set = collections.defaultdict(list)
            for s in sets:
                for c in s["components"]:
                    if c.get("page") == page:
                        ours_by_set[norm_set(s["set_number"])].append(c)
            ours_all = [c for cs in ours_by_set.values() for c in cs]
            gt_all = [c for s in gt["sets"] for c in s["components"]]
            gt_sets = {norm_set(s["set_number"]) for s in gt["sets"] if s.get("starts_on_page", True)}
            our_sets = {norm_set(s["set_number"]) for s in sets if any(l["page"] == page for l in s["location"])}
            b["gt_sets"] += len(gt_sets)
            b["sets_found"] += len(gt_sets & our_sets)
            b["gt_comps"] += len(gt_all)
            b["our_comps"] += len(ours_all)
            for g, o in align(gt_all, ours_all):
                b["matched"] += 1
                for f in FIELDS:
                    gv, ov = (g.get(f), o.get(f)) if f == "qty" else (norm(g.get(f)), norm(o.get(f)))
                    b[f"ok_{f}"] += gv == ov
                if norm(g.get("mfr")) and norm(o.get("finish")) == norm(g.get("mfr")) or \
                   norm(g.get("finish")) and norm(o.get("mfr")) == norm(g.get("finish")):
                    b["swaps"] += 1
        tot.update(b)
        rows.append((name, b))
    pct = lambda a, b: f"{100 * a / b:5.1f}" if b else "   - "
    print(f"{'book':9s} sets   comp_rec comp_prec " + " ".join(f"{f[:6]:>6s}" for f in FIELDS) + "  swaps")
    for name, b in rows + [("TOTAL", tot)]:
        print(f"{name:9s} {b['sets_found']:>2}/{b['gt_sets']:<3} {pct(b['matched'], b['gt_comps'])}    {pct(b['matched'], b['our_comps'])}    "
              + " ".join(f"{pct(b['ok_' + f], b['matched']):>6s}" for f in FIELDS) + f"  {b['swaps']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "oneshot_")
