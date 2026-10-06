# materialize structure labels: the model named run ids per field, code copies the text for each id
# usage: PYTHONPATH=. python alt_struct/convert.py [labels dir] [results dir]
import json, glob, os, re, sys, collections

SRC = sys.argv[1] if len(sys.argv) > 1 else "alt_struct/out"
DST = sys.argv[2] if len(sys.argv) > 2 else "out_struct"
INPUT = "alt_struct/input" if "dump" not in SRC else "alt_struct/dump_input"
FIELDS = ("qty", "description", "catalog", "finish", "mfr")
MAKER = re.compile(r"^(.*?)\s+-\s+(.*)$")


def text_of(ids, meta):
    runs = sorted((meta[str(i)] for i in ids if str(i) in meta), key=lambda r: (r["line"], r["x0"]))
    t = " ".join(r["text"] for r in runs)
    # a run ending in a hyphen continues the same token on the next line
    return re.sub(r"(?<=\w-) (?=\S)", "", t) or None


out = collections.defaultdict(list)
stat = collections.Counter()
for f in sorted(glob.glob(f"{SRC}/*.json")):
    name = os.path.basename(f)[:-5]
    book, p = re.match(r"(\w+)_p(\d+)$", name).groups()
    p = int(p)
    meta = json.load(open(f"{INPUT}/{name}.meta.json"))
    try:
        d = json.load(open(f))
    except Exception:
        stat["bad_json"] += 1
        continue
    for s in d.get("sets", []):
        starts = s.get("starts_on_page", True)
        comps = []
        for r in s.get("rows", []):
            ids = [i for fld in FIELDS for i in (r.get(fld) or [])]
            stat["ids"] += len(ids)
            stat["bad_ids"] += sum(str(i) not in meta for i in ids)
            c = {fld: text_of(r.get(fld) or [], meta) for fld in FIELDS}
            # qty and description often share one run of text, so a leading quantity on the description is the qty
            if not c["qty"] and c["description"]:
                m = re.match(r"^(\d{1,4}(?:\.0+)?|_+|--)\s+(.*)$", c["description"])
                if m:
                    c["qty"], c["description"] = m.group(1), m.group(2)
            # unit words share a run with the quantity ("1 Set") or the description ("Ea. Hinge")
            UNIT = r"(EA|Ea|EACH|SET|Set|PR|Pr|PAIR|LOT|EA-R)\.?"
            if c["qty"]:
                c["qty"] = re.sub(rf"\s+{UNIT}$", "", c["qty"]).strip()
            if c["description"]:
                c["description"] = re.sub(rf"^{UNIT}\s+", "", c["description"]).strip() or None
            q = c["qty"]
            c["qty"] = int(float(q)) if q and re.fullmatch(r"\d{1,4}(\.0+)?", q) else None
            if c["catalog"] and not c["mfr"]:
                m = MAKER.match(c["catalog"])
                if m and len(m.group(1).split()) <= 5 and re.match(r"^[A-Z][A-Za-z /&]+$", m.group(1)):
                    c["mfr"], c["catalog"] = m.group(1), m.group(2)
            c["page"] = p
            comps.append(c)
        num = s.get("set_number") or "CONTINUED"
        out[book].append({"set_number": num, "status": s.get("status", "active"),
                          "location": [{"page": p - 1}, {"page": p}] if not starts else [{"page": p}], "components": comps})
os.makedirs(DST, exist_ok=True)
for book, sets in out.items():
    json.dump({"sets": sets}, open(f"{DST}/{book}.json", "w"))
print(f"{sum(len(v) for v in out.values())} sets, {stat['ids']} run ids referenced, {stat['bad_ids']} not on the page, bad json files: {stat['bad_json']}")
