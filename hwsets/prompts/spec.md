You write a small JSON layout spec for the door hardware schedule in a construction spec PDF, from the sample pages below. Reply with the JSON only.

Dump format: each line of the page is one row; each run of words is prefixed with its left x in PDF points, e.g. `[66]1 [76]Continuous Hinge(s) [212]780-112HD x LAR [482]CLR [536]HA`. Pages are marked `=== page N ===`. These are the densest schedule pages of the book; other pages hold sets with slightly different content, so be permissive where the book could vary.

A hardware set is a named group (e.g. "Hardware Group No. 18", "Set #AL 01", "Set: 2.0", "HW E21 ...", "Heading #3", or "1.2" in a SET column) followed by component rows with qty, description, catalog number, finish code, manufacturer code, notes.

There are two spec modes.

COLUMNS mode (whitespace-aligned layouts):
- `set_header` (regex, required, Python re.search on the full line text): starts a new set. Named group `num` = set number (required); optional group `desc` = heading text on the same line. Make `num` permissive about the shapes set numbers take in this book (letters, hyphens, dots, suffixes). Allow plural and singular spellings of the header words.
- `row_start` (regex, required, re.match on the FIRST word of a line): a line whose first word matches and sits in the first column starts a new component. Usually the qty, e.g. `^\d{1,3}$`; widen it if quantities look like `3.0` or `__`.
- `columns` (required): list of {"field": one of qty|unit|description|catalog|finish|mfr|notes, "x": left edge}. Each word goes to the column with the largest x <= word.x0 + 4. The first column must be the qty column. Use x values 1-2pt left of the observed column starts. If qty and description appear as one run (e.g. `[94]1 Continuous Hinge`), estimate the description start a few points right of the qty. Omit fields the book does not have. When a unit word (EA, Ea., PR, SET, LOT) follows the quantity as its own run, give it a `unit` column, so it does not end up inside the description.
- `valign`: "top" if a wrapped cell's extra lines come BELOW the row's first line; "middle" if multi-line cells are vertically centered so some wrapped text appears ABOVE the qty line. Default "top".
- `skip` (list of regexes, re.search): lines to drop entirely: running page headers/footers, page numbers, column heading rows, copyright lines. Never a pattern that could match a component row.
- `set_meta` (regex, optional): lines between a set header and its first component that belong to the header block (door numbers, "Provide each SGL door(s) with the following:", "Description: ...", "Each Opening to Receive:"). Keep it specific; a pattern that matches any capitalized line will swallow component rows.
- `note_line` (regex, optional): lines that are notes attached to the component above (e.g. `^NOTE:`).
- `end` (list of regexes, optional): a line matching ends the schedule (e.g. `END OF SECTION`).
- Built-in: lines that fill a description cell plus the finish/mfr column, aligned to columns, start a component even without a qty (qty null). Other non-matching lines inside a set become set notes.

GRID mode (ruled tables with header labels):
- {"mode": "grid", "set_column": header label of the set-number column, "set_number": regex matching a set-number cell, "columns": {header label as printed: field}, "mfr_split": separator if manufacturer and product share one cell like "IVES - 5BB1"}. Fields: description, product (combined mfr+catalog cell), catalog, qty, finish, notes.
