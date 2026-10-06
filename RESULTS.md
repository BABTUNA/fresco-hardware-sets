# Benchmark results

Scored with the strict exact-match scorer on 155 labeled pages (311 sets, 2,218 rows) from 20 books, using the end-to-end pipeline output in `experiments/out_e2e/`. How the benchmark works is in [BENCHMARK.md](BENCHMARK.md). These numbers are after the interpreter fixes of 2026-10-05 (struck text, wraps vs notes, rows with no qty, door lines, column drift, centered pre-lines).

## Summary

| | Result |
| :--- | ---: |
| Sets fully correct (every row exact, nothing extra, status right) | 91.0% |
| Sets fully correct, pages the spec writer never saw | 90.4% |
| Exact rows | 97.6% |
| Exact rows, pages the spec writer never saw | 97.4% |
| Precision | 97.9% |
| Per-book average of exact rows | 98.1% |
| Sets found on labeled pages | 99.0% |
| NOT USED and moved status right | 93.8% |
| Mfr/finish swaps | 4 of 2,218 |
| Checks | 48/49 |
| Set numbers printed in the PDFs that we output, all 20 books | 1,171 of 1,175 (99.7%) |

| Tier | n | Exact rows | qty | description | catalog | finish | mfr |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| T0 trivial | 459 | 98.7 | 100.0 | 100.0 | 98.7 | 100.0 | 98.7 |
| T1 one caveat | 669 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| T2 hard | 1,090 | 95.6 | 98.5 | 97.7 | 96.7 | 97.6 | 97.2 |

The weakest areas are column drift (88.2% exact rows) and wrapped cells (94.6%), and both are mostly Star, whose catalog cells are full sentences. The T0 misses are Bridgeport, where the labels split `IVES` out of `IVES 69 / 63` and we keep it in the catalog.

## Whole-book check

`experiments/reconcile.py` scans every page of every book for set-header lines with one broad pattern that does not use our specs or page finder, then compares the set numbers it finds with ours.

| | Count |
| :--- | ---: |
| Set numbers printed in the 20 PDFs | 1,175 |
| Of those, in our output | 1,171 |
| Set numbers we output | 1,172 |

The four not in our output are Gerrard `AL 01`, which we save as `AL`, Star `01` and `102.1`, two more header spellings (`Hardware Set/Group #01`, `Hardware Group/Sets 102.1`), and Livelle `S52`, which is product text (`Hardware Group S52 Series, 200 pound capacity`) rather than a set.

## Sets fully correct

A set counts only when it was found, every labeled row in it is exact, we added no rows to it, and a NOT USED or moved status matches.

| | n | Right |
| :--- | ---: | ---: |
| Sets whose header is on a labeled page | 311 | 91.0 |
| Same, pages the spec writer never saw | 292 | 90.4 |
| Continued pieces (set started on an earlier page) | 31 | 83.9 |

Per book: star 56% of 18, bridgeport 65% of 17, gerrard 86% of 14, hfh 86% of 21, morris 86% of 7, jcryan 88% of 25, valor 92% of 24, sat 95% of 19, livelle 95% of 20, sjc 98% of 51, and 100% in the other 10 books.

## By caveat

| Tag | n | Source books | Exact rows | qty | description | catalog | finish | mfr | Swaps |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ambiguous_code | 548 | 16 | 96.0 | 98.4 | 97.1 | 97.3 | 97.3 | 97.3 | 0 |
| centered_cells | 29 | 1: JC Ryan | 96.6 | 100.0 | 96.6 | 100.0 | 100.0 | 100.0 | 0 |
| column_drift | 262 | 4: Forest, JC Ryan, Morris, Star | 88.2 | 94.7 | 93.9 | 91.2 | 90.8 | 89.3 | 4 |
| dense_page | 486 | 9 | 99.0 | 100.0 | 99.8 | 99.2 | 100.0 | 99.2 | 0 |
| embedded_mfr | 134 | 1: Roselle | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0 |
| empty_code | 419 | 18 | 97.1 | 98.8 | 98.1 | 97.9 | 99.0 | 98.6 | 0 |
| full_name_mfr | 134 | 2: JC Ryan, Star | 92.5 | 98.5 | 98.5 | 94.8 | 94.8 | 92.5 | 4 |
| grid_table | 134 | 1: Roselle | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0 |
| missing_qty | 107 | 8 | 95.3 | 96.3 | 96.3 | 96.3 | 96.3 | 95.3 | 0 |
| multi_page | 291 | 10 | 96.9 | 99.7 | 98.6 | 97.3 | 99.7 | 99.7 | 0 |
| struck_page | 392 | 3: HFH, SJC, Valor | 97.7 | 100.0 | 99.5 | 98.2 | 100.0 | 100.0 | 0 |
| wrapped | 672 | 18 | 94.6 | 98.5 | 97.0 | 96.1 | 97.3 | 97.2 | 4 |

Source books counts the distinct sample projects behind each tag. Several hard caveats come from only 1 to 3 books, and for most of them those are the only books in the whole corpus that have the caveat: JC Ryan is the only book with centered cells, Roselle the only ruled grid, Lyons and SJC the only books with NOT USED lines, and HFH, SJC and Valor the only books with struck text. A score on those tags measures how well we read those books, not the caveat in general.

## Sets

| Tag | n | Source books | Found | Status right |
| :--- | ---: | :--- | ---: | ---: |
| All | 311 | 20 | 99.0 | 93.8 |
| column_drift | 39 | 4: Forest, JC Ryan, Morris, Star | 94.9 | |
| dense_page | 103 | 9 | 100.0 | 100.0 |
| moved | 5 | 1: SJC | 100.0 | 100.0 |
| multi_page | 25 | 8 | 100.0 | |
| not_used | 11 | 2: Lyons, SJC | 90.9 | 90.9 |
| struck_page | 63 | 3: HFH, SJC, Valor | 98.4 | 91.7 |

The one NOT USED set we miss is SJC E01 on page 734, where the whole block including the header is struck through, so the header is dropped with it.

## By book

| Book | n | Exact rows | qty | description | catalog | finish | mfr |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ami | 90 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| bridgeport | 109 | 94.5 | 100.0 | 100.0 | 94.5 | 100.0 | 94.5 |
| doorco | 74 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| forest | 5 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| gerrard | 166 | 98.8 | 100.0 | 98.8 | 100.0 | 100.0 | 100.0 |
| hfh | 206 | 95.6 | 99.0 | 99.0 | 95.6 | 99.0 | 99.0 |
| jcryan | 155 | 96.8 | 98.7 | 98.7 | 96.8 | 98.7 | 96.8 |
| livelle | 132 | 98.5 | 100.0 | 98.5 | 98.5 | 100.0 | 100.0 |
| lyons | 83 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| marketview | 90 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| morris | 48 | 97.9 | 100.0 | 100.0 | 97.9 | 100.0 | 100.0 |
| national | 51 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| oswego | 120 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| roselle | 134 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| sat | 146 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| shubie | 31 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| sjc | 281 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| star | 150 | 82.0 | 92.0 | 90.0 | 87.3 | 85.3 | 84.7 |
| usi | 10 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| valor | 137 | 98.5 | 100.0 | 98.5 | 100.0 | 100.0 | 100.0 |

## What the errors are

| Error | Where | Tag it hurts |
| :--- | :--- | :--- |
| Prose catalog cells, with the finish and maker written inside the sentence | Star | column_drift, full_name_mfr, the 4 swaps |
| The label splits `IVES` out of `IVES 69 / 63 As Required`, we keep it in the catalog | Bridgeport | catalog, mfr |
| A fully struck block drops its own header, so the NOT USED set is lost | SJC E01 | not_used |
| Set `AL 01` saved as `AL`, because the header regex does not allow a space in the number | Gerrard | checks (1 of 49) |
| A few wrapped catalog lines in centered-cell books still attach to the wrong row | JC Ryan, HFH | wrapped, centered_cells |

## Before the fixes

For comparison, the same scorer on the output before the 2026-10-05 interpreter fixes.

| | Before | After |
| :--- | ---: | ---: |
| Sets fully correct | 70.7% | 91.0% |
| Exact rows | 94.2% | 97.6% |
| Precision | 91.5% | 97.9% |
| missing_qty exact rows | 69.2% | 95.3% |
| column_drift exact rows | 81.7% | 88.2% |
| struck_page exact rows | 92.9% | 97.7% |
| NOT USED and moved status right | 75.0% | 93.8% |
| Checks | 45/49 | 48/49 |

The fixes were written against this benchmark's errors. They are general rules in the interpreter, not per-book code, but a fresh set of labeled pages would confirm that the numbers hold on data they were not tuned on.
