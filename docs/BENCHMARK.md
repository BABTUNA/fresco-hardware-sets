# Benchmark

The benchmark measures how close the extractor's output is to a hand-checked answer key, and splits the result into easy and hard cases so a good overall number cannot hide a broken caveat.

It has three parts:

| Part | What it is | Size |
| :--- | :--- | :--- |
| **Answer key** | Labeled PDF pages, every set and component written down from the page image | 155 pages, 311 sets, 2,218 components, 20 books |
| **Scorer** | Compares our output to the labels by exact match, set by set, and reports by tier and caveat | `bench.py` |
| **Checks** | Pass/fail tests for single facts, one caveat each | 28 caveat checks + 21 no-set books |

All code is in `experiments/`. Page numbers in label file names are 0-based (`oswego_p417` is PDF page 418). Results are in [RESULTS.md](RESULTS.md).

## The books

Short names used in this doc and in the label file names. Schedule pages are the pages that list sets and their rows, as found by the page finder.

| Name | Project | PDF pages | Schedule pages | Labeled pages | Labeled components |
| :--- | :--- | ---: | ---: | ---: | ---: |
| ami | AMI, ATC renovation | 611 | 23 | 5 | 90 |
| bridgeport | 81-85 Bridgeport | 49 | 44 | 10 | 109 |
| doorco | The Door Company, Vantage TX-22 | 470 | 32 | 5 | 74 |
| forest | Forest Park School | 344 | 2 | 2 | 5 |
| gerrard | 2353 Gerrard Street Shelter | 36 | 19 | 7 | 166 |
| hfh | HFH DG Hospital | 184 | 159 | 16 | 206 |
| jcryan | JC Ryan 2 | 46 | 21 | 15 | 155 |
| livelle | Livelle Mulholland Life Plan Community | 1,191 | 58 | 8 | 132 |
| lyons | Lyons Township HS | 309 | 10 | 7 | 83 |
| marketview | Market View Apartments | 1,053 | 11 | 5 | 90 |
| morris | Morris Bank | 722 | 39 | 7 | 48 |
| national | National Doors and Hardware | 566 | 6 | 4 | 51 |
| oswego | Village of Oswego Public Works | 584 | 28 | 9 | 120 |
| roselle | Roselle Public Library | 17 | 3 | 2 | 134 |
| sat | SAT TDP | 3,930 | 122 | 8 | 146 |
| shubie | Shubie Center | 201 | 2 | 2 | 31 |
| sjc | SJC Well Behavioral | 2,320 | 39 | 20 | 281 |
| star | StarHardware, Commons Lane | 113 | 63 | 13 | 150 |
| usi | USI, Radnet Building | 1,460 | 1 | 3 | 10 |
| valor | Valor Acres Building E | 18 | 12 | 7 | 137 |

Five books have fewer than 5 labeled pages. Forest Park and Shubie have only 2 schedule pages. USI has 1, and its other 2 labeled pages are prose pages from round 1, labeled empty. Roselle and National have more schedule pages, but the rest are pages the spec writer saw, which round 3 skips.

The 21 PDFs with no hardware sets are not in this table. They are companion sections from these projects (wood doors, glazing, mirrors), Livelle volumes 2 to 4, the HFH door index, and the whole Woodridge Public Works manual. Each one has a check that it comes back empty.

## 1. The answer key

### What a label looks like

One JSON file per page in `eval/gt/`. Oswego, `eval/gt/oswego_p417.json`, set 02 (shortened):

```json
{"page_image": "oswego_p417.png",
 "sets": [{
   "set_number": "02",
   "starts_on_page": true,
   "continues_on_next_page": false,
   "status": "active",
   "components": [
     {"qty": 2, "description": "PIVOT SET", "catalog": "7215 SET", "finish": "626", "mfr": "IVE"},
     {"qty": null, "description": "SEALS - AS TESTED BY DOOR MANUFACTURER", "catalog": "BY DOOR / FRAME MANUFACTURER", "finish": null, "mfr": null}
   ]}]}
```

`status` is `active`, `not_used` or `moved`. `starts_on_page: false` means the set's header is on an earlier page.

### How labels are made

A separate Claude agent labels each page from its rendered image only, following `LABEL_PROMPT.md`. It never sees the text layer or our output. Codes are copied as printed, a blank or `__` quantity is `null`, door lists and notes are not components, and struck-through text is left out.

### Which pages

155 schedule pages, picked in three rounds. Each round covered a gap the one before left.

**Round 1, 39 pages:** about 2 random schedule pages per book. Most schedule pages are easy, so this gave a first number but few caveats.

**Round 2, 42 pages:** one search of the PDF text per caveat.

| Caveat | Search | Example found |
| :--- | :--- | :--- |
| NOT USED sets | lines with `NOT USED` or `MOVED TO` | Lyons: `Hardware Group No. 05 - Not Used` |
| Mfr vs finish | rows ending in a short code like `PE`, `NO`, `A` | Livelle: `1 Surface Closer ... 689 NO` |
| Missing qty | rows starting with `__` or `--` | Star: `__ Ea. Hinges 5BB1HW ...` |
| Multi-page sets | a set that runs onto the next page, both pages labeled | JC Ryan set EX-2.0, pages 24 and 25 |
| Set boundaries | pages with 4 or more sets | Roselle page 15 |
| Unsampled layouts | one page from every page run not sampled yet | Morris pages 233 to 263 |

**Round 3, 74 pages:** every book gets at least 5 labeled pages where it has that many unseen (SAT had 3 for 178 sets), and the thin caveats get targeted pages, found by searching the text and scanning the drawing marks and column positions of every schedule page.

| Area | Labeled before round 3 | After | Where the labels come from |
| :--- | ---: | ---: | :--- |
| Centered cells | 2 components | 29 | JC Ryan 29 |
| NOT USED and moved sets | 6 sets | 16 | SJC 12, Lyons 4 |
| Full manufacturer names | 7 components | 134 | JC Ryan 128, Star 6 |
| Struck text | 127 components | 392 | SJC 193, HFH 101, Valor 98 |
| Column drift | 41 components | 262 | JC Ryan 125, Star 108, Morris 27, Forest 2 |
| Missing qty | 60 components | 107 | Roselle 34, JC Ryan 28, SJC 20, Star 12, Livelle 6, HFH 5, National 1, Oswego 1 |

**Why search the PDF text.** Every search runs on the PDF's own text or drawing marks, not on our extractor's output. Picking pages from our output would only find cases the parser already recognizes. Round 2's multi-page and dense-page picks are the exception: they used our output to find candidates. Round 3 does not.

### How we know the labels are right

| Test | Result |
| :--- | :--- |
| **Agreement.** 12 pages labeled twice by independent labelers (`bench_agreement.py`) | 100% of sets, 99.4% of components, 100% of fields agree. The one difference is whether HFH's `DIAGRAMS` row is a component. |
| **Grounding.** Every labeled catalog, finish and mfr value is looked up in that page's text layer (`bench_grounding.py`) | 5,497 of 5,511 values appear word for word. All 14 exceptions are part numbers that wrap at a hyphen (`...CON-` and `SNB` on two lines), which the label joins correctly. |
| **Hand review.** Every disagreement between our output and a label was read by hand | 3 label errors found and fixed. All three were the labeler "correcting" a printed code (`SI6X` written as `SR64`). |
| **Review screen.** The viewer at `/#review` (no button, a URL) lists every disagreement between the output and a label, shows the page with the row boxed and the two rows side by side, and records a verdict per item (label wrong, extractor wrong, both acceptable) in `experiments/eval/review.json`. | 58 disagreements on the 155 pages at the last run. |
| **Consistency.** One convention was applied two ways in Bridgeport, which has no mfr column: the labelers split `IVES` out of `IVES 69 / 63` as the manufacturer but left `Horton` inside `Horton 4100 LH Pull Series`. The 4 Horton rows were changed to match the 6 IVES rows, so a maker name printed in the catalog cell is the manufacturer. | 4 rows edited on 2026-10-06. |

Agreement measures consistency, not truth. Both labelers are the same model, so they could share a blind spot. The grounding test is the independent check on correctness.

## 2. The scorer

`bench.py` compares our output to the labels with exact matches only. There are no similarity scores and no cutoffs.

| Rule | What it means | Example |
| :--- | :--- | :--- |
| **Group by set** | Rows are only compared inside the same set. A set carried over from the previous page is compared with the set we carried over. | Labeled set 02 rows are only checked against our set 02 rows |
| **Rows** | A labeled row is right only if one of our rows in the set has all 5 fields equal | Label `2 PIVOT SET 7215 SET 626 IVE`. If ours said finish `630`, the row is wrong |
| **Fields** | Each field on its own: is the labeled value anywhere in our set? Shows which field broke. | In that case qty, description, catalog and mfr are still right, only finish is wrong |
| **Equal** | qty must be identical (`null` only equals `null`). Text ignores case, spaces and quote styles. | `4.5 x 4.5` = `4.5 X 4.5`, `36″` = `36"` |
| **Swaps** | A labeled mfr shows up in our finish column, or the reverse | Star p56: label finish `625`, ours mfr `625` |

**Example.** Oswego page 418, set 02, where we merged two rows into one:

```
labels   MULLION SEAL                             139N PSA                      ZER
         SEALS - AS TESTED BY DOOR MANUFACTURER   BY DOOR / FRAME MANUFACTURER
ours     MULLION SEAL SEALS - AS TESTED BY ...    139N PSA BY DOOR / FRAME ...  ZER
```

Both labeled rows are wrong, and the merged row counts against precision.

**Tag.** Each labeled component gets the caveats it exercises. Tags come from the label and the source page, never from our output, so our misses still land in the right bucket. Tags are computed once and frozen in `eval/tags.json` (see below), so the scorer only reads them.

| Tag | Applies when | Level |
| :--- | :--- | :--- |
| `ambiguous_code` | The label's mfr or finish is a 1 or 2 letter code (`PE`, `NO`, `A`, `IV`) | component |
| `missing_qty` | The label's qty is null | component |
| `empty_code` | Finish or mfr is null in a book that has that column | component |
| `wrapped` | The label's text is not all on the source line the row starts on | component |
| `full_name_mfr` | The mfr is a name like `Pemko`, not a code | component |
| `centered_cells` | Wrapped, in a book whose cells are vertically centered (JC Ryan) | component |
| `grid_table`, `embedded_mfr` | Ruled table, mfr inside the product cell (Roselle) | book |
| `struck_page` | 2 or more words on the page have a line through them | page |
| `column_drift` | This page's finish or mfr column sits more than 8pt from the spec, or most rows have no word at the spec's position | page |
| `not_used`, `moved` | The label's set status | set |
| `multi_page` | The set started on an earlier page or continues on the next | set |
| `dense_page` | The page has 4 or more sets | set |

**Tier.**

| Tier | Rule | Example |
| :--- | :--- | :--- |
| T0 trivial | No tags | `6 EA HINGE 5BB1HW 4.5 X 4.5 652 IVE` |
| T1 one caveat | Exactly one tag, not a hard one | the same row with qty `__` |
| T2 hard | Two or more tags, or any of `centered_cells`, `grid_table`, `embedded_mfr`, `struck_page`, `column_drift` | a wrapped catalog on a page with drifted columns |

`dense_page` is reported as a tag but does not count toward the tier.

**Frozen tags.** `bench_tags.py` computes every tag and tier and writes them to `eval/tags.json`, one entry per labeled page, with components in label file order. The two rows from the label example above:

```json
{"description": "PIVOT SET", "tags": [], "tier": "T0 trivial"}
{"description": "SEALS - AS TESTED BY DOOR MANUFACTURER", "tags": ["empty_code", "missing_qty", "wrapped"], "tier": "T2 hard"}
```

Freezing keeps the buckets fixed between runs, so a spec change cannot move a row from one tier to another. If a label is added or edited, `bench.py` stops and asks you to rerun `bench_tags.py`.

**Report.**

| Number | Meaning |
| :--- | :--- |
| Exact rows | labeled rows with every field right, out of all labeled rows |
| Field accuracy | labeled values found in the right set, out of all labeled rows |
| Swaps | labeled mfr or finish values found in the other column |
| Precision | our rows that exactly match a labeled row, out of all our rows on labeled pages |
| Sets found | labeled sets we found by set number, plus whether NOT USED and moved sets got the right status |

The first three are reported for every bucket: all rows, each tier, each tag, each book, and pages the spec writer never saw.

## 3. The checks

`eval/checks.json` holds one fact per check, with the expected value read from the raw PDF text:

```json
{"id": "pe-is-pemko", "caveat": "mfr_vs_finish", "book": "morris", "set": "106.38",
 "desc": "^Continuous Hinge", "expect": {"mfr": "PE", "finish": null, "catalog": "K10BEFM95HD1"}}
```

Checks can test a row's fields, a set's status, count or pages, or that something is not extracted. The 21 PDFs without sets must come back empty.

```
PASS  mfr_vs_finish   pe-is-pemko
PASS  not_used        lyons-05
FAIL  set_boundaries  no-door-lines        found 27: ['Single Door #102 ...']
FAIL  revisions       struck-row-gasketing found 1: ['GASKETING SET']
```

| Caveat | Passed |
| :--- | ---: |
| Mfr vs finish | 5/5 |
| NOT USED | 6/6 |
| Missing qty | 5/5 |
| Set boundaries | 5/5 |
| Multi-page | 1/1 |
| Column layouts | 4/4 |
| Revisions (struck text) | 2/2 |
| No-set books | 21/21 |
| **Total** | **49/49** |

All 49 pass. The last failure, Gerrard's `Set #AL 01` read as set `AL`, was fixed on 2026-10-06.

## 4. Running it

From `experiments/`:

```bash
uvx --from pdfplumber python3 e2e.py .r1
```

```bash
uvx --from pdfplumber python3 bench.py
```

```bash
uvx --from pdfplumber python3 bench_checks.py
```

`e2e.py` writes our output for all 20 books to `out_e2e/`. The other commands read it. After adding or editing labels, refreeze the tags first:

```bash
uvx --from pdfplumber python3 bench_tags.py
```

| File | Job |
| :--- | :--- |
| `bench_tags.py`, `eval/tags.json` | Computes and freezes tags and tiers |
| `bench.py` | Exact scoring against the labels and frozen tags, prints the tables |
| `bench_checks.py`, `eval/checks.json` | Pass/fail checks and no-set books |
| `eval/bench_misses.json` | Every wrong row and missed set from the last run, with the fields that broke |
| `bench_errors.py` | Every wrong row next to our most similar row, grouped by book (`FULL=1` for all). Debugging only |
| `bench_agreement.py` | Labeler agreement on `eval/gt2/` |
| `bench_grounding.py` | Labels against the text layer |
| `bench_select.py`, `bench_select2.py` | Page selection for rounds 2 and 3 |
| `LABEL_PROMPT.md` | Labeler instructions |
| `eval/gt/`, `eval/gt2/`, `eval/pages/` | Labels, second labels, page images |

## 5. Limits

- **Locations are not scored yet.** The benchmark checks fields, not bboxes. The plan is DocILE-style: a component's location counts as right when the center of every labeled word falls inside our box.
- **`continues_on_next_page` is a guess** when a page ends in blank space. It only affects the `multi_page` tag.
- **The drift tag uses our spec** to decide where columns should be. It describes the page relative to what we expected, not an absolute property of the page.
- **Exact match is strict on purpose.** One wrong word fails the whole row, and label conventions count too, for example whether a wrapped part number keeps a space after its hyphen. Normalization covers case, spaces, quotes and hyphen spacing, nothing more.
- **Some tags are still small.** `moved` has 5 sets and `centered_cells` has 29 components.
- **Struck rows are excluded from the labels.** Until struck-text detection is built, every struck row we extract counts against precision.
- **The headline excludes 154 components** on 7 labeled pages the spec writer saw: Forest Park and Shubie (both of their 2 schedule pages), and one page each from Gerrard, Roselle and USI. Those books have so few schedule pages that there was little else to label.
