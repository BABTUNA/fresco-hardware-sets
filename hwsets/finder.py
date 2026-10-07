# which pages of a specbook hold hardware sets, without knowing the book's header wording
import re
import pypdfium2 as pdfium

# a component row: quantity, words, then one or two short codes at the end of the line
QTY = r"(?:\d{1,3}(?:\.0)?|__|--)"
ROW = re.compile(rf"^\s*{QTY}\s+(?:(?:EA|Ea\.?|EA\.|SET|Set|PR|Pr\.?|LOT)\s+)?[A-Za-z].{{3,}}?\s(?P<tail>(?:\S{{1,6}}\s+)?\S{{1,6}})\s*$")
CODE = re.compile(r"^(?:[A-Z][a-z]{2,12}|[A-Z]{2,5}|\d{3}[A-Z]?|US\d{1,2}[A-Z]?|\d{1,2}[A-Z]{1,2}|[A-Z]\d{2,3}|B/O|---|-+|BLK|[A-Z]{1,3}-[A-Z0-9]{1,3})$")
# door hardware vocabulary keeps other trades' equipment lists out
HARDWARE = re.compile(r"hinge|closer|lock|exit dev|panic|cylinder|core|stop|threshold|kick|pull|silencer|sweep|gasket|strike|pivot|bolt|holder|operator", re.I)
# grid tables extract in cell order, so also accept a hardware item next to a finish code
FINISH = re.compile(r"\b(?:6[0-9]{2}|US\d{1,2}[A-Z]?|\d{2}D)\b")
MIN_ROWS = 2


# "3   EA   HINGE   5BB1 4.5 X 4.5 NRP   652   IVE" -> True
# "B. Silencers and gasketing, where listed in Hardware Sets" -> False
def row_like(line):
    m = ROW.match(line)
    if m and CODE.match(m.group("tail").split()[-1]):
        return True
    return bool(FINISH.search(line) and HARDWARE.search(line) and re.search(r"(?:^|\s)\d{1,2}(?:\s|$)", line))


# raw text lines per page with pypdfium2, fast enough to read a 4,000 page book in seconds.
# used for scoring and header search, not for coordinates
def page_texts(path):
    pdf = pdfium.PdfDocument(path)
    return [pdf[i].get_textpage().get_text_range().splitlines() for i in range(len(pdf))]


# per page: how many row-like lines, and how many of those mention hardware
# input: texts [[line1, line2, ...], ...]  one list per page ouptut: scores [0, 0, 7, 12, 0, 9, 3, 0, 0, 1, 0], vocab [0, 0, 5, 8, 0, 6, 2, 0, 0, 1, 0]
def page_scores(texts):
    scores, vocab = [], []
    for lines in texts:
        rows = [l for l in lines if row_like(l)]
        scores.append(len(rows))
        vocab.append(sum(bool(HARDWARE.search(l)) for l in rows))
    return scores, vocab


# pages with enough rows, joined into runs, allowing a short gap (a set's tail or a legend page)
#   in:  scores [0, 0, 7, 12, 0, 9, 3, 0, 0, 1, 0]   (one page per entry)
#   out: [[2, 6]]   a run from page 2 to page 6, 0-based, inclusive
def runs(scores, vocab, gap=1):
    hits = [i for i, s in enumerate(scores) if s >= MIN_ROWS]
    out = []
    for i in hits:
        if out and i - out[-1][1] <= gap + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    # a run starts one page early when that page also has rows (first set under the section intro)
    for r in out:
        if r[0] > 0 and scores[r[0] - 1] > 0:
            r[0] -= 1
        if r[1] + 1 < len(scores) and scores[r[1] + 1] > 0:
            r[1] += 1
    # a run needs real volume and hardware words, which drops other trades' equipment lists
    return [r for r in out if sum(scores[r[0]:r[1] + 1]) >= 5 and sum(vocab[r[0]:r[1] + 1]) >= 3]


# the whole first layer: path -> (texts, scores, runs)
# find the schedule pages in a specbook without knowing the book's header wording, and without coordinates
def find_schedule(path):
    texts = page_texts(path)
    scores, vocab = page_scores(texts)
    return texts, scores, runs(scores, vocab)


# the compiled header regex is cheap to run over the whole book: pull in set pages the finder
# scored low because they have few row-shaped lines (an empty set, a set that is one NOTE line)
#   in:  runs [[417, 444]], a header match on page 446
#   out: [417, 418, ..., 444, 445, 446]
def widen_with_headers(spec, texts, runs, margin=3):
    pages = {p for a, b in runs for p in range(a, b + 1)}
    if spec.get("mode") == "grid":
        return sorted(pages)
    hdrs = [re.compile(h) for h in [spec["set_header"]] + spec.get("set_header_extra", [])]
    added = True
    while added:
        added = False
        for i, lines in enumerate(texts):
            if i in pages or not any(h.search(l.strip()) for l in lines for h in hdrs):
                continue
            if any(abs(i - p) <= margin for p in pages):
                pages.add(i); added = True
                # the page after a header page may hold that set's rows
                if i + 1 < len(texts) and any(row_like(l) for l in texts[i + 1]):
                    pages.add(i + 1)
    # fill small holes so a set never skips a page
    s = sorted(pages)
    for a, b in zip(s, s[1:]):
        if 1 < b - a <= 3:
            pages.update(range(a + 1, b))
    return sorted(pages)
