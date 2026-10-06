# pdfplumber words -> visual lines with coordinates
import re


def strike_marks(page):
    # thin horizontal rules on the page as (x0, x1, y). a rule through a word's middle is a strike-through,
    # one just under it is an underline, so the caller checks the height
    return [(o["x0"], o["x1"], (o["top"] + o["bottom"]) / 2) for o in page.lines + page.rects
            if o["bottom"] - o["top"] < 2.5 and o["x1"] - o["x0"] > 4]


def page_lines(page, ytol=2.5):
    # one pdfplumber page -> lines in reading order, each with its words and box
    #   in:  page 427 of oswego
    #   out: [{"top": 98.2, "bottom": 108.1, "x0": 80.1, "x1": 528.0,
    #          "text": "6 EA HINGE 5BB1HW 4.5 X 4.5 NRP 652 IVE",
    #          "words": [{"text": "6", "x0": 80.1, "x1": 85.3, "top": 98.2, "bottom": 108.1, "struck": False}, ...]}, ...]
    words = page.extract_words(extra_attrs=["upright", "size"], keep_blank_chars=False, x_tolerance=1.5)
    # rotated text is a watermark, private-use glyphs are icons
    words = [w for w in words if w["upright"] and not all(0xE000 <= ord(ch) <= 0xF8FF for ch in w["text"])]
    marks = strike_marks(page)
    for w in words:
        mid = (w["top"] + w["bottom"]) / 2
        w["struck"] = any(a <= w["x0"] + 1 and b >= w["x1"] - 1 and abs(y - mid) < 1.5 for a, b, y in marks)
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    lines = []
    for w in words:
        if lines and abs(lines[-1]["top"] - w["top"]) <= ytol:
            lines[-1]["words"].append(w)
            lines[-1]["bottom"] = max(lines[-1]["bottom"], w["bottom"])
        else:
            lines.append({"top": w["top"], "bottom": w["bottom"], "words": [w]})
    for l in lines:
        l["words"].sort(key=lambda w: w["x0"])
        # letter-spaced headings come out as single letters ("H W 06A"), join them back into one word.
        # only at the start of a line, since catalog numbers like "90S X J BKT" have real single letters
        merged = []
        for w in l["words"]:
            p = merged[-1] if merged else None
            if p and len(merged) == 1 and len(w["text"]) == 1 and w["text"].isalpha() and re.fullmatch(r"[A-Z]+", p["text"]) \
                    and len(p["text"]) <= 3 and p.get("spaced", len(p["text"]) == 1) and w["x0"] - p["x1"] < 4:
                merged[-1] = dict(p, text=p["text"] + w["text"], x1=w["x1"], spaced=True)
            else:
                merged.append(w)
        l["words"] = merged
        l["text"] = " ".join(w["text"] for w in l["words"])
        l["x0"] = l["words"][0]["x0"]
        l["x1"] = max(w["x1"] for w in l["words"])
    return lines
