# does the extraction fit the book? cheap checks on the result that catch a wrong spec
import re, collections
from .lines import page_lines
from .finder import row_like

FINISH_SHAPE = re.compile(r"^(?:6\d\d[A-Z]?|US\d{1,2}[A-Z]?|\d{2}[A-Z]{1,2}|BLK|BK|BLACK|AL|ALM|CLR|MIL|A|AA|DKB|GRY|SP\d+|PC|PRIME|PRIMED|\d{3}-\d{3})$", re.I)
FIELDS = ("qty", "description", "catalog", "finish", "mfr")


# the plain words a header regex starts with, so near misses can be searched for
#   "^Hardware Groups?/Sets?\s*#" -> "Hardware Group"   (stops at the first regex operator)
def literal_prefix(regex):
    m = re.match(r"\^?(?:\(\?i\))?\\?s?\*?((?:[A-Za-z #:]|\\[.#:]|\\s[+*]?)+)", regex)
    p = m.group(1) if m else ""
    # "Groups?": the letter before a "?" is optional, leave it out
    if m and regex[m.end():m.end() + 1] == "?":
        p = p[:-1]
    p = re.sub(r"\\s[+*]?", " ", p).replace("\\", "").strip()
    return p if len(p) >= 2 else None


# -> list of flags, each {"check": name, "count": n, "examples": [...]}
#   [{"check": "header_near_miss", "count": 10, "examples": [[96, "Hardware Group No.103 [BULLETIN 023]"]]}]
def audit(spec, sets, texts, pages, scores, pdf=None):
    flags = []
    if spec.get("mode") != "grid":
        # lines that start like the header but did not match it: a spelling the spec writer never saw
        pre = literal_prefix(spec["set_header"])
        hdr = re.compile(spec["set_header"])
        skip = [re.compile(x) for x in spec.get("skip", [])]
        if pre:
            miss = [(i, l.strip()) for i in pages for l in texts[i]
                    if re.search(r"(?<![A-Za-z])" + re.escape(pre) + r"(?![A-Za-z]).{0,6}\d", l, re.I)
                    and not hdr.search(l.strip()) and not re.match(r"\s*(\d{1,4}|_+|-{2})\s", l)
                    and not any(x.search(l.strip()) for x in skip)]
            if miss:
                flags.append({"check": "header_near_miss", "count": len(miss), "examples": miss[:6]})
    comps = [c for s in sets for c in s["components"]]
    by_page = collections.Counter(c["page"] for c in comps)
    # pages full of row-shaped lines and nothing extracted from them. the raw text cannot see strike-through,
    # so a page whose rows are all struck (a revised-out set) is checked with the page geometry and let through
    orphan = [i for i in pages if scores[i] >= 3 and by_page[i] == 0]
    if pdf is not None:
        orphan = [i for i in orphan if sum(row_like(l["text"]) and not any(w["struck"] for w in l["words"])
                                           for l in page_lines(pdf.pages[i])) >= 3]
    if orphan:
        # the repair call only sees the sample pages, so show it what these pages hold
        examples = [(i, [l.strip() for l in texts[i] if l.strip()][:12]) for i in orphan[:3]]
        flags.append({"check": "rows_without_components", "count": len(orphan), "examples": examples})
    if comps:
        # 4+ words in finish or mfr means a column x is wrong
        long_codes = [c for c in comps if any(c.get(f) and len(re.sub(r"\(.*?\)", "", c[f]).split()) > 3 for f in ("finish", "mfr"))]
        if len(long_codes) > 0.1 * len(comps):
            flags.append({"check": "long_text_in_code_columns", "count": len(long_codes),
                          "examples": [{k: c.get(k) for k in FIELDS} for c in long_codes[:3]]})
        # an mfr column full of 626, US26D, BLK means the columns are swapped
        fin = [c["finish"] for c in comps if c.get("finish")]
        mfr = [c["mfr"] for c in comps if c.get("mfr")]
        f_rate = sum(bool(FINISH_SHAPE.match(v)) for v in fin) / max(len(fin), 1)
        m_rate = sum(bool(FINISH_SHAPE.match(v)) for v in mfr) / max(len(mfr), 1)
        if mfr and m_rate > 0.5 and m_rate > f_rate:
            flags.append({"check": "mfr_looks_like_finish", "count": len(mfr), "examples": mfr[:6]})
        # far fewer components than row-shaped lines
        expected = sum(scores[i] for i in pages)
        if expected and len(comps) < 0.6 * expected:
            flags.append({"check": "low_coverage", "count": len(comps), "examples": [f"{len(comps)} components for {expected} row-like lines"]})
        # a door-number line read as a row: qty 115 with no catalog
        odd = [c for c in comps if (c.get("qty") or 0) > 99 and not c.get("catalog")]
        if odd:
            flags.append({"check": "suspicious_qty", "count": len(odd), "examples": [{k: c.get(k) for k in FIELDS} for c in odd[:3]]})
    empty = [s["set_number"] for s in sets if not s["components"] and not s.get("status")]
    if len(empty) > max(2, 0.15 * len(sets)):
        flags.append({"check": "many_empty_sets", "count": len(empty), "examples": empty[:8]})
    return flags
