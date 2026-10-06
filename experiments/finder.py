# find hardware schedule page runs in a whole specbook without knowing its format
# a component row looks like: quantity, words, then short codes at the end of the line
import re, sys, json
import pypdfium2 as pdfium

QTY = r"(?:\d{1,3}(?:\.0)?|__|--)"
ROW = re.compile(rf"^\s*{QTY}\s+(?:(?:EA|Ea\.?|EA\.|SET|Set|PR|Pr\.?|LOT)\s+)?[A-Za-z].{{3,}}?\s(?P<tail>(?:\S{{1,6}}\s+)?\S{{1,6}})\s*$")
CODE = re.compile(r"^(?:[A-Z][a-z]{2,12}|[A-Z]{2,5}|\d{3}[A-Z]?|US\d{1,2}[A-Z]?|\d{1,2}[A-Z]{1,2}|[A-Z]\d{2,3}|B/O|---|-+|BLK|[A-Z]{1,3}-[A-Z0-9]{1,3})$")
# door hardware vocabulary keeps other trades' equipment lists out
HARDWARE = re.compile(r"hinge|closer|lock|exit dev|panic|cylinder|core|stop|threshold|kick|pull|silencer|sweep|gasket|strike|pivot|bolt|holder|operator", re.I)
# grid tables extract in cell order, so also accept a hardware item next to a finish code
FINISH = re.compile(r"\b(?:6[0-9]{2}|US\d{1,2}[A-Z]?|\d{2}D)\b")
MIN_ROWS = 2


def row_like(line):
    m = ROW.match(line)
    if m and CODE.match(m.group("tail").split()[-1]):
        return True
    return bool(FINISH.search(line) and HARDWARE.search(line) and re.search(r"(?:^|\s)\d{1,2}(?:\s|$)", line))


def page_scores(path):
    pdf = pdfium.PdfDocument(path)
    scores, vocab = [], []
    for i in range(len(pdf)):
        rows = [l for l in pdf[i].get_textpage().get_text_range().splitlines() if row_like(l)]
        scores.append(len(rows))
        vocab.append(sum(bool(HARDWARE.search(l)) for l in rows))
    return scores, vocab


def runs(scores, vocab, gap=1):
    # contiguous pages with enough rows, allowing short gaps (a set's tail or a legend page)
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
    return [r for r in out if sum(scores[r[0]:r[1] + 1]) >= 5 and sum(vocab[r[0]:r[1] + 1]) >= 3]


if __name__ == "__main__":
    s, v = page_scores(sys.argv[1])
    print(json.dumps({"pages": len(s), "runs": runs(s, v)}))
