# Benchmark results

Scored with the strict exact-match scorer on 155 labeled pages (311 sets, 2,218 rows) from 20 books, using the end-to-end pipeline output in `experiments/out_e2e/`. How the benchmark works is in [BENCHMARK.md](BENCHMARK.md). These numbers are after the interpreter fixes of 2026-10-05 and 2026-10-06 (struck text, wraps vs notes, rows with no qty, door lines, column drift, centered pre-lines, joint column calibration, split codes, run continuity, maker names split out of the catalog in books with no mfr column, description-only wraps, letter-plus-digit set numbers).

## Summary

| | Result |
| :--- | ---: |
| Sets fully correct (every row exact, nothing extra, status right) | 94.5% (held-out set: 89.5%) |
| Sets fully correct, pages the spec writer never saw | 94.5% |
| Exact rows | 98.5% (held-out set: 97.2%) |
| Exact rows, pages the spec writer never saw | 98.4% |
| Precision | 98.6% |
| Per-book average of exact rows | 98.9% |
| Sets found on labeled pages | 99.4% |
| NOT USED and moved status right | 93.8% |
| Mfr/finish swaps | 0 of 2,218 |
| Checks | 49/49 |
| Set numbers printed in the PDFs that we output, all 20 books | 1,172 of 1,175 (99.7%) |

| Tier | n | Exact rows | qty | description | catalog | finish | mfr |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| T0 trivial | 456 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| T1 one caveat | 671 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| T2 hard | 1,091 | 96.9 | 99.2 | 98.5 | 97.3 | 98.9 | 98.4 |

The weakest areas are column drift (93.1% exact rows) and wrapped cells (95.5%), and both are mostly Star, whose catalog cells are full sentences. The T0 misses are Bridgeport, where the labels split `IVES` out of `IVES 69 / 63` and we keep it in the catalog.

## Held-out set

Every one of the 155 pages above was used to find and fix bugs, so a separate set of 25 pages was labeled afterwards and scored once, with no changes made after seeing the result. The pages were picked on 2026-10-06 from schedule pages that had never been labeled and that the spec writer never saw: one from every book that still had such a page (15 books), plus 10 more spread by book size. Labels and frozen tags are in `experiments/eval/holdout/`.

| | Tuned set (155 pages) | Held-out set (25 pages) |
| :--- | ---: | ---: |
| Sets | 311 | 38 |
| Rows | 2,218 | 360 |
| Sets fully correct | 94.5% | 89.5% |
| Exact rows | 98.5% | 97.2% |
| Precision | 98.6% | 97.2% |
| Mfr/finish swaps | 0 | 0 |
| T0 trivial rows | 100.0% | 100.0% |
| T1 one caveat rows | 100.0% | 100.0% |
| T2 hard rows | 96.8% | 92.8% |

The held-out numbers are the ones to quote. Rows hold up (1.2 points lower), and sets drop 5 points, which with 38 sets is 2 sets: 3 of 4 Star sets and 1 of 2 HFH sets, the two books that were weakest on the tuned set as well. Every other book is at 100% on both. The tuned set is what the fixes were developed against, so its number is the optimistic one.

To run it: `GT=eval/holdout/gt python bench_tags.py` once, then `GT=eval/holdout/gt python bench.py`.

## Whole-book check

`experiments/reconcile.py` scans every page of every book for set-header lines with one broad pattern that does not use our specs or page finder, then compares the set numbers it finds with ours.

| | Count |
| :--- | ---: |
| Set numbers printed in the 20 PDFs | 1,175 |
| Of those, in our output | 1,172 |
| Set numbers we output | 1,173 |

The three not in our output are Star `01` and `102.1`, two more header spellings (`Hardware Set/Group #01`, `Hardware Group/Sets 102.1`), and Livelle `S52`, which is product text (`Hardware Group S52 Series, 200 pound capacity`) rather than a set.

## Sets fully correct

A set counts only when it was found, every labeled row in it is exact, we added no rows to it, and a NOT USED or moved status matches.

| | n | Right |
| :--- | ---: | ---: |
| Sets whose header is on a labeled page | 311 | 94.9 |
| Same, pages the spec writer never saw | 292 | 94.5 |
| Continued pieces (set started on an earlier page) | 31 | 80.6 |

Per book: star 78% of 18, hfh 86% of 21, morris 86% of 7, jcryan 88% of 25, oswego 92% of 12, valor 92% of 24, livelle 95% of 20, sjc 98% of 51, and 100% in the other 12 books.

## By caveat

| Tag | n | Source books | Exact rows | qty | description | catalog | finish | mfr | Swaps |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ambiguous_code | 548 | 16 | 98.5 | 99.3 | 98.7 | 98.5 | 99.3 | 99.3 | 0 |
| centered_cells | 29 | 1: JC Ryan | 96.6 | 100.0 | 96.6 | 100.0 | 100.0 | 100.0 | 0 |
| column_drift | 262 | 4: Forest, JC Ryan, Morris, Star | 93.5 | 97.7 | 97.3 | 94.7 | 96.6 | 94.3 | 0 |
| dense_page | 486 | 9 | 99.8 | 100.0 | 99.8 | 100.0 | 100.0 | 100.0 | 0 |
| embedded_mfr | 134 | 1: Roselle | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0 |
| empty_code | 419 | 18 | 97.6 | 99.3 | 98.6 | 97.9 | 99.3 | 98.8 | 0 |
| full_name_mfr | 138 | 2: JC Ryan, Star | 92.8 | 98.6 | 98.6 | 94.9 | 96.4 | 92.8 | 0 |
| grid_table | 134 | 1: Roselle | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0 |
| missing_qty | 107 | 8 | 95.3 | 95.3 | 95.3 | 95.3 | 97.2 | 95.3 | 0 |
| multi_page | 291 | 10 | 96.6 | 99.3 | 98.3 | 96.9 | 99.3 | 99.3 | 0 |
| struck_page | 392 | 3: HFH, SJC, Valor | 97.4 | 99.7 | 99.2 | 98.0 | 99.7 | 99.7 | 0 |
| wrapped | 672 | 18 | 96.1 | 99.3 | 98.2 | 97.0 | 98.8 | 98.4 | 0 |

Source books counts the distinct sample projects behind each tag. Several hard caveats come from only 1 to 3 books, and for most of them those are the only books in the whole corpus that have the caveat: JC Ryan is the only book with centered cells, Roselle the only ruled grid, Lyons and SJC the only books with NOT USED lines, and HFH, SJC and Valor the only books with struck text. A score on those tags measures how well we read those books, not the caveat in general.

## Sets

| Tag | n | Source books | Found | Status right |
| :--- | ---: | :--- | ---: | ---: |
| All | 311 | 20 | 99.4 | 93.8 |
| column_drift | 39 | 4: Forest, JC Ryan, Morris, Star | 97.4 |  |
| dense_page | 103 | 9 | 100.0 | 100.0 |
| moved | 5 | 1: SJC | 100.0 | 100.0 |
| multi_page | 25 | 8 | 100.0 |  |
| not_used | 11 | 2: Lyons, SJC | 90.9 | 90.9 |
| struck_page | 63 | 3: HFH, SJC, Valor | 98.4 | 91.7 |

The one NOT USED set we miss is SJC E01 on page 734, where the whole block including the header is struck through, so the header is dropped with it.

## By book

| Book | n | Exact rows | qty | description | catalog | finish | mfr |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ami | 90 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| bridgeport | 109 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| doorco | 74 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| forest | 5 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| gerrard | 166 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| hfh | 206 | 95.1 | 98.5 | 98.5 | 95.1 | 98.5 | 98.5 |
| jcryan | 155 | 96.8 | 98.7 | 98.7 | 96.8 | 98.7 | 96.8 |
| livelle | 132 | 98.5 | 100.0 | 98.5 | 98.5 | 100.0 | 100.0 |
| lyons | 83 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| marketview | 90 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| morris | 48 | 97.9 | 100.0 | 100.0 | 97.9 | 100.0 | 100.0 |
| national | 51 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| oswego | 120 | 99.2 | 100.0 | 99.2 | 99.2 | 100.0 | 100.0 |
| roselle | 134 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| sat | 146 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| shubie | 31 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| sjc | 281 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| star | 150 | 91.3 | 97.3 | 96.0 | 93.3 | 95.3 | 93.3 |
| usi | 10 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| valor | 137 | 98.5 | 100.0 | 98.5 | 100.0 | 100.0 | 100.0 |

## What the errors are

| Error | Where | Tag it hurts |
| :--- | :--- | :--- |
| Prose cells, with the finish and maker written inside the sentence (`Trimco`, `625 polished chrome`). The labels pull them out, we leave them in the catalog. | Star page 56 | full_name_mfr |
| A ragged wrap that looks like a row with no quantity: `WIRE HARNESS` / `CONNECTOR - IN FRAME`, broken early by the author with room left on the line | Oswego page 445 | wrapped |
| A fully struck block drops its own header, so the NOT USED set is lost | SJC E01 | not_used |
| The labeler corrected the PDF's own typo (`celling` to `ceiling`) | Star pages 80 and 103 | catalog |

## Before the fixes

The same scorer on the output before the interpreter fixes of 2026-10-05 and 2026-10-06.

| | Before | After |
| :--- | ---: | ---: |
| Sets fully correct | 70.7% | 94.9% |
| Exact rows | 94.2% | 98.5% |
| Precision | 91.5% | 98.6% |
| Mfr/finish swaps | 4 | 0 |
| missing_qty exact rows | 69.2% | 95.3% |
| column_drift exact rows | 81.7% | 93.5% |
| struck_page exact rows | 92.9% | 97.4% |
| Star, sets fully correct | 56% | 72% |
| Bridgeport, sets fully correct | 65% | 100% |
| Gerrard, sets fully correct | 86% | 100% |
| NOT USED and moved status right | 75.0% | 93.8% |
| Checks | 45/49 | 49/49 |

The fixes were written against this benchmark's errors. They are general rules in the interpreter, not per-book code, plus one spec repair for Star (its header regex was anchored to the line start and one page puts the header mid-line). A fresh set of labeled pages would confirm that the numbers hold on data they were not tuned on.
