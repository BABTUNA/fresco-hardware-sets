# Caveats

The brief lists six cases where a simple extractor breaks. Below is each one with a real example from the sample PDFs, what the pipeline does about it, and how it scores on the benchmark (81 labeled pages, 1,103 components). Page numbers are PDF pages, starting at 1.

| Caveat | Status |
| :--- | :--- |
| 1. Manufacturer vs finish codes | Solved |
| 2. Set boundaries | Mostly |
| 3. NOT USED sets | Solved |
| 4. Multi-page sets | Solved |
| 5. Different column layouts | Mostly |
| 6. Missing quantities | Partly |
| Extra: crossed-out revisions | Not built yet |

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

**What we do.** The spec says what a set header looks like in that book. A ruled table like Roselle's uses grid mode, where a number in the SET column starts a set. The audit then looks for lines that start like a header but did not match. That check caught 10 HFH sets that had been merged into their neighbors.

**How it scores.** 99.4% of labeled sets found (309 of 311), 100% of the 103 sets on dense pages with 4 or more per page. Across all 20 books, 1,174 of the 1,175 set numbers printed in the PDFs come out.

**Gaps.**
- Morris prints a door line under each header, `1 Single Door #104   Banking Personal 106 to/from Office 104   105° RH`. It starts with `1`, so it is read as a component. That happens 27 times.
- Lyons door lists like `326 327 330 334 337B` are read the same way.
- Gerrard's `Set #AL 01` comes out as set `AL` with description `01`, because the header regex does not allow a space in the number.

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

**How it scores.** All 6 NOT USED checks pass. Lyons has 4 NOT USED groups in its raw text and we found all 4. On the benchmark, 10 of the 11 labeled NOT USED sets come out with the right status.

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

**Gap.** Pages where the columns move more than 30 points are the weakest layout case at 93.5% of rows exact, next to full-name manufacturers at 92.8%. Morris's second layout and Star page 77 put the finish into the catalog or manufacturer field.

## 6. Missing quantities

**Example.** Quantities can be blank, `__`, `--`, or a phrase:

```
Star p73:     __   Ea.   Hinges        5BB1HW (size & quantity per 08 71 00)    622   IV
Roselle p15:  SILENCERS   IVES - SILENCER SI6X     --     BLACK
SJC p721:     As Req   Hinge-HT        CB51 HT                                  630   PBB
Oswego p427:           DIAGRAMS        PROVIDE FACTORY POINT TO POINT WIRING DIAGRAMS  B/O
```

**What we do.** All of these become `"qty": null`, never a guess. A row with no qty still starts a new component when it fills the description and manufacturer columns, like Oswego's DIAGRAMS row. `3.0` in Forest Park becomes `3`.

**How it scores.** All 5 missing-quantity checks pass. On the benchmark, 95.3% of the 107 rows with no quantity are exact.

**Gaps.**
- A row with no qty and no manufacturer gets merged into the row above. Oswego page 418: `SEALS - AS TESTED BY DOOR MANUFACTURER` ends up inside the MULLION SEAL row.
- SJC's `As Req` hinge rows are dropped.
- Bridgeport page 48 has real 4-digit quantities, `2571 Standard Hinge` for 857 apartments. The spec only accepts up to 3 digits, so the qty comes out null.

## Extra: crossed-out revisions

This one is not in the brief but shows up in 3 books. When a spec is revised, old rows are struck through instead of deleted. The text is still in the PDF.

**Example.** HFH page 103, set 110: `1 EA GASKETING SET 188SBK PSA [BULLETIN 023, 251218]` has a line drawn through it. Valor page 13 strikes a single word, `OFFICE STOREROOM LEVER LOCKSET`.

**What we do now.** Nothing yet, so struck rows come out as normal components. This is the largest source of extra components on the benchmark and fails both revision checks.

**Plan.** A thin horizontal line through a word's mid-height marks it struck. A probe already detects both the HFH row and the Valor word. A fully struck row is kept with status `removed`, and struck words inside a row are dropped.
