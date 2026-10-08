# Caveats

The brief lists six cases where a simple extractor breaks. Below is each one with a real example from the sample PDFs, what the pipeline does about it, and how it scores on the benchmark (155 labeled pages, 311 sets, 2,218 rows). Page numbers are PDF pages, starting at 1.

| Caveat | Status | On the benchmark |
| :--- | :--- | :--- |
| 1. Manufacturer vs finish codes | Solved | 0 swaps in 2,218 rows |
| 2. Set boundaries | Solved | 309 of 311 labeled sets found, 1,174 of 1,175 printed set numbers across the 20 books |
| 3. NOT USED sets | Solved | 10 of 11 labeled sets with the right status, 5 of 5 moved sets |
| 4. Multi-page sets | Solved | 25 of 25 labeled multi-page sets found |
| 5. Different column layouts | Mostly | 93.5% of rows exact where columns drift, 100% in grid tables |
| 6. Missing quantities | Solved | 95.3% of the 107 rows with no quantity exact |
| Extra: crossed-out revisions | Solved | 97.4% of rows exact on the 392 rows from pages with struck text |

## 1. Manufacturer vs finish codes

**Example.** Morris Bank, page 285, set 106.38:

```
1   Continuous Hinge   K10BEFM95HD1                     PE
1   Exit Device        31 PE8804 F LESS TRIM     10BE   SA
```

`PE` can mean Pemko (manufacturer) or Painted Enamel (finish). The first row has only one code, so the value alone does not say which it is.

**What we do.** The book's spec gives every column a role by position. In Morris the finish column starts at x=459 and the manufacturer column at x=506. `PE` sits at x=506, so it is the manufacturer. Every code in that column gets the same reading for the whole book.

```json
{"qty": 1, "description": "Continuous Hinge", "catalog_number": "K10BEFM95HD1", "finish": null, "mfr": "PE"}
```

**How it scores.** 0 manufacturer/finish swaps in 2,218 labeled rows. Across all 20 books:

| Code | Read as | Count | Books |
| :--- | :--- | ---: | :--- |
| `PE` | manufacturer (Pemko) | 319 | Livelle, Morris, USI |
| `NO` | manufacturer (Norton) | 23 | Livelle |
| `A` | finish (anodized) | 147 | 8 books |

`NO` example, Livelle page 643: `1 Surface Closer Cush Stop CA1601 P   689   NO`

## 2. Set boundaries

**Example.** Roselle, page 15. Thirteen sets on one page, and a new set only shows up as a new number in the SET column:

```
SET    HARDWARE TYPE     MANUFACTURER - PRODUCT       QTY  FINISH
1.3    MORTISE HINGE     IVES - 5BB1 4.5" x 4.5"      2    613 (OIL RUBBED BRONZE)
       PANIC HARDWARE    VON DUPRIN - 35A ...         1    613 (OIL RUBBED BRONZE)
1.4    MORTISE HINGE     IVES - 5BB1 4.5" x 4.5"      3    613 (OIL RUBBED BRONZE)
```

Other books mark sets with a header line, and the wording changes from book to book: `HARDWARE GROUP NO. 18`, `Set #AL 01`, `Set: 2.0`, `HW E21`, `Heading #3`. Some books even change it inside one book. HFH writes `Hardware Group No.103 [BULLETIN 023, 251218]` for revised sets, and Star mixes `Group/Set`, `Groups/Set` and `Set/Group`.

**What we do.** The spec says what a set header looks like in that book. A ruled table like Roselle's uses grid mode, where a number in the SET column starts a set. Lines that look like a row but are not, such as Morris's door line under each header (`1 Single Door #104   Banking Personal 106 to/from Office 104   105° RH`) or Lyons's door lists (`326 327 330 334 337B`), are set metadata in the spec and become the set's doors. The audit then looks for lines that start like a header but did not match. That check caught 10 HFH sets that had been merged into their neighbors.

**How it scores.** 99.4% of labeled sets found (309 of 311), 100% of the 103 sets on dense pages with 4 or more per page. Across all 20 books, 1,174 of the 1,175 set numbers printed in the PDFs come out.

**Gap.** The two labeled sets we miss are SJC E01, a NOT USED set whose whole block is struck through, header included, and one Star set whose header sits mid-line after a door reference.

## 3. NOT USED sets

**Example.** Lyons, pages 285 to 291:

```
Hardware Group No. 05 - Not Used
Hardware Group No. 16 - Not Used
```

SJC has a second kind, page 715:

```
HW 11   Moved to Exterior Set HW E14
```

**What we do.** The set is kept with no components and a status.

```json
{"set_number": "05", "status": "not_used", "components": []}
{"set_number": "11", "status": "moved", "moved_to": "E14", "components": []}
```

**How it scores.** All 6 NOT USED checks pass. Lyons has 4 NOT USED groups in its raw text and we found all 4. On the benchmark, 10 of the 11 labeled NOT USED sets come out with the right status, and all 5 moved sets do. The miss is SJC E01, struck through header and all.

## 4. Multi-page sets

**Example.** JC Ryan, set EX-2.0 starts at the bottom of page 24 and its last rows are at the top of page 25. Page 25 does not repeat the header.

**What we do.** Pages are read in order and rows keep going into the current set until a new header shows up. The set gets one location entry per page.

```json
"location": [{"page": 24, "bbox": [...]}, {"page": 25, "bbox": [...]}]
```

**How it scores.** 238 of the 1,178 extracted sets span a page break. All 25 labeled multi-page sets were found, with 96.6% of their rows exact. The continued piece is where it slips: 80.6% of those pieces are fully correct, against 94.9% of sets overall.

## 5. Different column layouts

**Example.** The same kind of hinge row in three books:

```
Oswego:   6   EA   HINGE              5BB1HW 4.5 X 4.5 - NRP     652   IVE
JC Ryan:  1   Continuous Hinge        CFMxxHD1-M                       Pemko
Roselle:  MORTISE HINGE | IVES - 5BB1 4.5" x 4.5" | 3 | 613 (OIL RUBBED BRONZE)
```

Oswego has a unit column. JC Ryan has no finish column and spells out manufacturer names. Roselle is a ruled table with the manufacturer glued to the product.

Rows also wrap differently. In Oswego a long cell continues on the lines below the row. In JC Ryan multi-line cells are centered, so part of the catalog number prints above the qty line:

```
1   Door Closer       UNI7500                              Norton
                      290_S (Finish to match door/frame
1   Jamb Gasketing                                         Pemko
                      color)
```

**What we do.** This is why there is one spec per book. Claude reads 2 sample pages and writes down that book's columns and wrap style. The interpreter handles both wrap styles, grid tables, and splitting `IVES - 5BB1` into manufacturer and catalog. Each page also re-snaps the catalog, finish and manufacturer columns to its own aligned edges, because columns move a few points between pages.

**How it scores.** Grid tables and embedded manufacturers are at 100% of rows exact, centered cells at 96.6%.

**Gap.** Pages where the columns move more than 30 points are the weakest layout case at 93.5% of rows exact, next to full-name manufacturers at 92.8%. Both are mostly Star, whose catalog cells are full sentences with the finish and maker written inside them (`in 622 finish by Trimco manufacturing`). The labels pull those out, we leave them in the catalog.

## 6. Missing quantities

**Example.** Quantities can be blank, `__`, `--`, or a phrase:

```
Star p73:     __   Ea.   Hinges        5BB1HW (size & quantity per 08 71 00)    622   IV
Roselle p15:  SILENCERS   IVES - SILENCER SI6X     --     BLACK
SJC p721:     As Req   Hinge-HT        CB51 HT                                  630   PBB
Oswego p427:           DIAGRAMS        PROVIDE FACTORY POINT TO POINT WIRING DIAGRAMS  B/O
```

**What we do.** All of these become `"qty": null`, never a guess. A row with no qty still starts a new component when it fills the description and a code column, like Oswego's DIAGRAMS row or its `SEALS - AS TESTED BY DOOR MANUFACTURER` row on page 418. `3.0` in Forest Park becomes `3`. Bridgeport's real 4-digit quantities (`2571 Standard Hinge`, for 857 apartments) stay numbers.

**How it scores.** All 5 missing-quantity checks pass. On the benchmark, 95.3% of the 107 rows with no quantity are exact.

**Gap.** A ragged wrap can look like a row with no quantity. Oswego page 445 breaks `WIRE HARNESS` / `CONNECTOR - IN FRAME` early with room left on the line, and we read the second line as its own row.

## Extra: crossed-out revisions

This one is not in the brief but shows up in 3 books. When a spec is revised, old rows are struck through instead of deleted. The text is still in the PDF.

**Example.** HFH page 103, set 110: `1 EA GASKETING SET 188SBK PSA [BULLETIN 023, 251218]` has a line drawn through it. Valor page 13 strikes a single word, `OFFICE STOREROOM LEVER LOCKSET`.

**What we do.** A thin horizontal rule through a word's mid-height marks it struck. A row whose first word is struck, or more than half of whose words are, is a revision and is dropped. Struck words inside a kept row are dropped, so Valor's row comes out as `STOREROOM LEVER LOCKSET`. The audit also knows which pages carry strike marks, so a book with revisions is not flagged for the rows it left out.

**How it scores.** Both revision checks pass. On the 392 labeled rows from pages with struck text, 97.4% are exact, and the HFH set 110 row above does not appear in the output.
