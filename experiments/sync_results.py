# rewrite the number tables in the docs from a saved bench.py output, so the docs never carry typed-in numbers
# usage: python sync_results.py <bench output file>
import re, sys

txt = open(sys.argv[1]).read()
ROOT = __file__.rsplit("/", 2)[0] + "/docs/"
BOOKS = ["ami", "bridgeport", "doorco", "forest", "gerrard", "hfh", "jcryan", "livelle", "lyons", "marketview",
         "morris", "national", "oswego", "roselle", "sat", "shubie", "sjc", "star", "usi", "valor"]
TAGS = ["ambiguous_code", "centered_cells", "column_drift", "dense_page", "embedded_mfr", "empty_code",
        "full_name_mfr", "grid_table", "missing_qty", "multi_page", "struck_page", "wrapped"]


def row(name):
    m = re.search(rf"^ *{re.escape(name)} +(\d+) +([\d.]+) +([\d.]+) +([\d.]+) +([\d.]+) +([\d.]+) +([\d.]+) +(\d+)$", txt, re.M)
    return m.groups()


def setrow(name):
    block = txt[txt.index("sets by caveat"):txt.index("sets fully correct")]
    m = re.search(rf"^{re.escape(name)} +(\d+) +([\d.]+) +([\d.\-]+)$", block, re.M)
    return m.group(1), m.group(2), ("" if m.group(3) == "-" else m.group(3))


def section(s, start, end):
    a = s.index(start)
    b = s.index(end, a) if end else len(s)
    return a, b


def replace_in(s, start, end, fn):
    a, b = section(s, start, end)
    return s[:a] + fn(s[a:b]) + s[b:]


all_ = row("ALL"); unseen = row("ALL unseen pages")
prec = re.search(r"row precision: \d+/\d+ = +([\d.]+)%", txt).group(1)
full = re.search(r"^sets +\d+ +([\d.]+)$", txt, re.M).group(1)
full_u = re.search(r"^sets \(unseen pages\) +\d+ +([\d.]+)$", txt, re.M).group(1)
cont = re.search(r"^continued pieces +\d+ +([\d.]+)$", txt, re.M).group(1)
avg = re.search(r"^per-book average +\d+ +([\d.]+)", txt, re.M).group(1)
perbook = re.search(r"^  per book: (.*)$", txt, re.M).group(1)
perbook = re.sub(r", (?=[a-z]+ 100% of)(.*)$", lambda m: ", and 100% in the other " + str(m.group(1).count("100%")) + " books", perbook, count=1)
sets_all = setrow("ALL")

# RESULTS.md
p = ROOT + "RESULTS.md"; s = open(p).read()
def summary(t):
    t = re.sub(r"^\| Sets fully correct \(every row exact, nothing extra, status right\) \| [\d.]+% \|", f"| Sets fully correct (every row exact, nothing extra, status right) | {full}% |", t, flags=re.M)
    t = re.sub(r"^\| Sets fully correct, pages the spec writer never saw \| [\d.]+% \|", f"| Sets fully correct, pages the spec writer never saw | {full_u}% |", t, flags=re.M)
    t = re.sub(r"^\| Exact rows \| [\d.]+% \|", f"| Exact rows | {all_[1]}% |", t, flags=re.M)
    t = re.sub(r"^\| Exact rows, pages the spec writer never saw \| [\d.]+% \|", f"| Exact rows, pages the spec writer never saw | {unseen[1]}% |", t, flags=re.M)
    t = re.sub(r"^\| Precision \| [\d.]+% \|", f"| Precision | {prec}% |", t, flags=re.M)
    t = re.sub(r"^\| Per-book average of exact rows \| [\d.]+% \|", f"| Per-book average of exact rows | {avg}% |", t, flags=re.M)
    t = re.sub(r"^\| Sets found on labeled pages \| [\d.]+% \|", f"| Sets found on labeled pages | {sets_all[1]}% |", t, flags=re.M)
    t = re.sub(r"^\| NOT USED and moved status right \| [\d.]+% \|", f"| NOT USED and moved status right | {sets_all[2]}% |", t, flags=re.M)
    t = re.sub(r"^\| Mfr/finish swaps \| \d+ of 2,218 \|", f"| Mfr/finish swaps | {all_[7]} of 2,218 |", t, flags=re.M)
    for name in ("T0 trivial", "T1 one caveat", "T2 hard"):
        r = row(name)
        t = re.sub(rf"^\| {name} \| [\d,]+ \|.*$", f"| {name} | {int(r[0]):,} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |", t, flags=re.M)
    return t
s = replace_in(s, "## Summary", "## Whole-book check", summary)
def fully(t):
    t = re.sub(r"^\| Sets whose header is on a labeled page \| 311 \| [\d.]+ \|", f"| Sets whose header is on a labeled page | 311 | {full} |", t, flags=re.M)
    t = re.sub(r"^\| Same, pages the spec writer never saw \| 292 \| [\d.]+ \|", f"| Same, pages the spec writer never saw | 292 | {full_u} |", t, flags=re.M)
    t = re.sub(r"^\| Continued pieces \(set started on an earlier page\) \| 31 \| [\d.]+ \|", f"| Continued pieces (set started on an earlier page) | 31 | {cont} |", t, flags=re.M)
    t = re.sub(r"^Per book: .*$", f"Per book: {perbook}.", t, flags=re.M)
    return t
s = replace_in(s, "## Sets fully correct", "## By caveat", fully)
def caveat(t):
    for tag in TAGS:
        r = row(tag)
        t = re.sub(rf"^\| {tag} \| \d+ \| ([^|]+) \|.*$", lambda m: f"| {tag} | {r[0]} | {m.group(1).strip()} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} |", t, flags=re.M)
    return t
s = replace_in(s, "## By caveat", "## Sets\n", caveat)
def sets(t):
    for tag, label in (("ALL", "All"), ("column_drift", "column_drift"), ("dense_page", "dense_page"), ("moved", "moved"), ("multi_page", "multi_page"), ("not_used", "not_used"), ("struck_page", "struck_page")):
        n, found, st = setrow(tag)
        t = re.sub(rf"^\| {label} \| \d+ \| ([^|]+) \|.*$", lambda m: f"| {label} | {n} | {m.group(1).strip()} | {found} | {st} |", t, flags=re.M)
    return t
s = replace_in(s, "## Sets\n", "## By book", sets)
def books(t):
    for b in BOOKS:
        r = row(b)
        t = re.sub(rf"^\| {b} \| \d+ \|.*$", f"| {b} | {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |", t, flags=re.M)
    return t
s = replace_in(s, "## By book", "## What the errors are", books)
def before(t):
    t = re.sub(r"^(\| Sets fully correct \| [\d.]+% \| )[\d.]+% \|", rf"\g<1>{full}% |", t, flags=re.M)
    t = re.sub(r"^(\| Exact rows \| [\d.]+% \| )[\d.]+% \|", rf"\g<1>{all_[1]}% |", t, flags=re.M)
    t = re.sub(r"^(\| Precision \| [\d.]+% \| )[\d.]+% \|", rf"\g<1>{prec}% |", t, flags=re.M)
    t = re.sub(r"^(\| Mfr/finish swaps \| \d+ \| )\d+ \|", rf"\g<1>{all_[7]} |", t, flags=re.M)
    for tag in ("missing_qty", "column_drift", "struck_page"):
        t = re.sub(rf"^(\| {tag} exact rows \| [\d.]+% \| )[\d.]+% \|", rf"\g<1>{row(tag)[1]}% |", t, flags=re.M)
    t = re.sub(r"^(\| NOT USED and moved status right \| [\d.]+% \| )[\d.]+% \|", rf"\g<1>{sets_all[2]}% |", t, flags=re.M)
    return t
s = replace_in(s, "## Before the fixes", None, before)
open(p, "w").write(s)

# APPROACH_RESULTS.md, the "ours" column of the main table: percent with its fraction
p = ROOT + "APPROACH_RESULTS.md"; s = open(p).read()
matched = re.search(r"row precision: (\d+)/\d+", txt).group(1)
n_sets = round(float(full) / 100 * int(sets_all[0]))
s = re.sub(r"^\| Exact rows \| [^|]+ \|", f"| Exact rows | {all_[1]}% ({int(matched):,} / {int(all_[0]):,}) |", s, flags=re.M)
s = re.sub(r"^\| Sets fully correct \| [^|]+ \|", f"| Sets fully correct | {full}% ({n_sets} / {sets_all[0]}) |", s, flags=re.M)
s = re.sub(r"^\| Mfr/finish swaps \| [^|]+ \|", f"| Mfr/finish swaps | {all_[7]} |", s, flags=re.M)
open(p, "w").write(s)

# README and PLAN headline sentences
p = ROOT + "../README.md"; s = open(p).read()
s = re.sub(r"[\d.]+% of the 2,218 labeled rows come out exactly right with every field correct, and [\d.]+% of the 311 sets are fully correct\.",
           f"{all_[1]}% of the 2,218 labeled rows come out exactly right with every field correct, and {full}% of the 311 sets are fully correct.", s)
open(p, "w").write(s)
p = ROOT + "PLAN.md"; s = open(p).read()
s = re.sub(r"[\d.]+% of sets fully correct, [\d.]+% of rows exact, [\d.]+% precision, \d+ mfr/finish swaps in 2,218 rows\.",
           f"{full}% of sets fully correct, {all_[1]}% of rows exact, {prec}% precision, {all_[7]} mfr/finish swaps in 2,218 rows.", s)
open(p, "w").write(s)
print(f"synced: sets {full}%, rows {all_[1]}%, precision {prec}%, swaps {all_[7]}")
