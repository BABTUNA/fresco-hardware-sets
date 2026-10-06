# words -> visual lines with coordinates, dropping rotated (watermark) text
import pdfplumber

def page_lines(page, ytol=2.5):
    words = page.extract_words(extra_attrs=["upright", "size"], keep_blank_chars=False, x_tolerance=1.5)
    words = [w for w in words if w["upright"] and not all(0xE000 <= ord(ch) <= 0xF8FF for ch in w["text"])]
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
        l["text"] = " ".join(w["text"] for w in l["words"])
        l["x0"] = l["words"][0]["x0"]
        l["x1"] = max(w["x1"] for w in l["words"])
    return lines
