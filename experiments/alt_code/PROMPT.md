You are the "parser writer" in an experiment. For each book you get one sample dump of its two densest door hardware schedule pages. Write a Python parser for that book. This simulates ONE LLM call per book: do not run code, do not open PDFs, images or other files, read only the dump files named in your task.

Dump format: each printed line, with each run of words prefixed by its left x in PDF points, e.g. `[66]1 [76]Continuous Hinge(s) [212]780-112HD x LAR [482]CLR [536]HA`. Pages are marked `=== page N ===`. The book's other schedule pages use the same layout but different content; your parser runs on all of them, plus up to 2 pages of section prose before and after.

Write experiments/alt_code/parsers/<book>.py defining:

    def parse(pages):
        ...
        return sets

`pages` is a list of dicts in reading order: {"page": int, "lines": [line, ...]}. Each line is {"text": str, "x0", "x1", "top", "bottom": float, "words": [{"text", "x0", "x1", "top", "bottom"}]}, words sorted left to right, lines sorted top to bottom. Coordinates are PDF points, origin top left. Rotated watermark text is already removed.

Return a list of sets, each:
{"set_number": "18", "description": str or None, "status": "active" | "not_used" | "moved", "first_page": int,
 "components": [{"qty": int or None, "description", "catalog", "finish", "mfr": str or None, "page": int}]}

Rules for the values: copy codes exactly as printed. qty is null when no quantity is printed (blank, "__", "--", "As Req"); "3.0" is 3. Drop unit words (EA, Ea., SET). Join a cell's wrapped lines with one space. Door lists, door/opening description lines, notes paragraphs, operational descriptions, legend tables, column headings and running page headers/footers are not components. A set whose header is on an earlier page continues onto later pages until the next set header. A set marked NOT USED / N/A is "not_used"; one that says "Moved to ..." is "moved". If manufacturer and catalog share a cell like "IVES - 5BB1", mfr is "IVES" and catalog "5BB1".

Use only the Python standard library (re is fine). Write general code for the layout you see, not code keyed to the sample's exact strings or set numbers. Reply in under 120 words: per book one line on the hardest part.
