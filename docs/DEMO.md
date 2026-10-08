# Demo script

About 4 minutes. Two books in two different formats, one unseen PDF dropped in, every bonus item shown once. Run `scripts/demo_reset.sh` first, then `uv run hwsets serve`, then open http://localhost:8000 at full width.

Say the words in the right column roughly as written. Do the clicks in the left column.

## 0:00 The idea (20 s)

| Do | Say |
| :--- | :--- |
| Library screen is open | Every specbook uses one layout for all its sets. So instead of sending every page to a model, a model reads two schedule pages once and writes a short layout spec for the book, and plain code reads every page with it. One call per book, deterministic after that, and every value comes from real words on the page with a bounding box. |

## 0:20 An unseen book (30 s)

| Do | Say |
| :--- | :--- |
| Drag `out/demo/Valor Acres - Door Hardware.pdf` from Finder onto the drop zone | Drop in a PDF the system has never seen. It finds the schedule pages, one model call writes the layout spec, the interpreter reads every page. |
| Wait for the book view (about 20 s). Click a row in the table | 37 sets. Click a row and it lights up on the page. The box is where the value came from. |
| Click "All books" | |

## 0:50 Example 1, Livelle: columns and the mfr vs finish problem (70 s)

| Do | Say |
| :--- | :--- |
| Search `livelle`, open `2025-12-12_Livelle_Bid_Set_Project_Manual_Vol1_rev1.pdf` | This is a 1,191-page project manual. 58 of those pages hold sets, in a dealer format: "Set: 1.0", qty, description, catalog, finish, maker. |
| Set 1.0 is open, page 643. Point at the row `Surface Closer Cush Stop, CA1601 P, 689, NO` | Here is the caveat from the brief. `NO` could be Norton or the word "No". `PE` in the row above could be Pemko or painted enamel. We never decide that from the value. The spec says the column at this x is the manufacturer column, so every code in it is a maker, for all 1,304 rows in the book. Zero finish/maker swaps on the benchmark. |
| Open the set dropdown, pick Set 4.0 (pages 644 to 645). Click the last row, then the next-page arrow | Sets run across page breaks. This set starts on 644 and its last rows are on 645. Same set, two boxes. |
| Point at the CONF column | Every row carries a confidence: its weakest field, from whether the value looks like its column, whether the column snapped to the page, whether the row had a quantity. Under 0.8 is amber. |

## 2:00 Example 2, Gerrard: a different format, the legend, and fixing mistakes (80 s)

| Do | Say |
| :--- | :--- |
| All books, search `Hdw Spec`, open `Hdw Spec & Sch-IFT_5.pdf` | A completely different book: a hardware dealer's schedule, "Set #AL 01", doors listed under the header, 35 sets on 36 pages. Same code, a different spec. |
| Point at the pill "19 codes in the book's legend", then at `HA` and `CLR` in the table | This book prints a legend before its sets. The extractor reads it, so `HA` is Hager Companies and `CLR` is Clear Anodized, and an option code in a catalog number like `LAR` resolves to Length as Required. No hardcoded dictionary, it comes off the page. |
| Pick Set 24 from the dropdown. Point at the red `0.60` on the Battery Backup row | Here the confidence does its job: the finish cell says "No" and the score flags it. |
| Double-click the finish cell, type `No Finish`, Enter | Fix one value: double-click, type, done. It is kept in a corrections file and survives every rerun. |
| Click "Adjust columns" | For a mistake that hits every row, nobody edits a regex. The columns are lines on the page. Drag one and apply, and the whole book is re-read with no model call. |
| Click "Cancel". Click "All books" | |

## 3:20 Tag a line, and the numbers (40 s)

| Do | Say |
| :--- | :--- |
| Search `star`, open it. Type `107` in the page box next to the page title and press Enter | Star writes some headers as "Hardware Group/Sets". The model's spec missed this one, so 102.1 was swallowed into set 102. |
| Click "Tag a line", click the line `Hardware Group/Sets 102.1`, choose "This starts a set" | Click the line, say what it is. That becomes a literal rule in the spec and the book reruns. |
| Point at the new `Set 102.1` box and the dropdown | There it is, 15 rows. The same box underneath takes a sentence instead ("the set on this page is missing") and sends it to the model, when the click is not enough. |
| Back on the library screen | On 155 labeled pages from 20 books, scored strictly with every field exact: 98.5% of rows, 94.9% of sets fully correct. Held out: 98.6% of rows. Across all 20 books, 1,174 of the 1,175 printed set numbers come out. Code, specs, labels and the benchmark are in the repo. |

## After recording

The reset put Star's spec back to its pre-feedback version in the working tree. `git checkout specs/` restores the committed one (with the two feedback rules), and `rm -rf corrections data/uploads` clears what the demo added.

## If something goes wrong

- The drop-in takes longer than 30 s: keep talking, the Valor book is 18 pages and the call is the wait.
- Tag a line says the book is a ruled table: you opened Roselle, not Star.
- The Battery Backup cell is already blue: the reset was not run, `scripts/demo_reset.sh` clears corrections.
