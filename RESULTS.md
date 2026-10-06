# Benchmark results

Scored with the strict exact-match scorer on 155 labeled pages (311 sets, 2,218 rows) from 20 books, using the end-to-end pipeline output in `experiments/out_e2e/`. How the benchmark works is in [BENCHMARK.md](BENCHMARK.md).

## Summary

| | Result |
| :--- | ---: |
| Exact rows | 94.2% |
| Exact rows, pages the spec writer never saw | 93.8% |
| Precision | 91.5% |
| Per-book average of exact rows | 94.6% |
| Sets found | 98.4% |
| NOT USED and moved status right | 75.0% |
| Mfr/finish swaps | 4 of 2,218 |
| Checks | 45/49 |

| Tier | n | Exact rows | qty | description | catalog | finish | mfr |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| T0 trivial | 459 | 97.6 | 98.9 | 100.0 | 98.7 | 100.0 | 98.7 |
| T1 one caveat | 669 | 97.0 | 99.0 | 97.3 | 98.7 | 98.8 | 99.0 |
| T2 hard | 1,090 | 91.0 | 97.2 | 95.5 | 92.2 | 95.0 | 96.0 |

The weakest areas, in order: missing quantities (69.2% exact), column drift (81.7%), and struck-through revisions. Most T0 misses are Bridgeport, where 4-digit quantities are not read and the manufacturer sits inside the catalog text.

## By caveat

| Tag | n | Source books | Exact rows | qty | description | catalog | finish | mfr | Swaps |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ambiguous_code | 548 | 16 | 92.3 | 98.4 | 96.9 | 93.4 | 94.7 | 97.4 | 0 |
| centered_cells | 29 | 1: JC Ryan | 93.1 | 100.0 | 96.6 | 96.6 | 100.0 | 96.6 | 0 |
| column_drift | 262 | 4: Forest, JC Ryan, Morris, Star | 81.7 | 95.0 | 92.4 | 85.1 | 85.9 | 90.1 | 4 |
| dense_page | 486 | 9 | 94.7 | 97.3 | 97.3 | 96.3 | 98.1 | 97.3 | 0 |
| embedded_mfr | 134 | 1: Roselle | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0 |
| empty_code | 419 | 18 | 90.5 | 97.4 | 92.6 | 93.1 | 97.6 | 97.1 | 0 |
| full_name_mfr | 134 | 2: JC Ryan, Star | 93.3 | 99.3 | 100.0 | 96.3 | 95.5 | 93.3 | 4 |
| grid_table | 134 | 1: Roselle | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0 |
| missing_qty | 107 | 8 | 69.2 | 74.8 | 74.8 | 70.1 | 86.9 | 78.5 | 0 |
| multi_page | 291 | 10 | 94.2 | 98.6 | 96.9 | 94.5 | 99.0 | 98.6 | 0 |
| struck_page | 392 | 3: HFH, SJC, Valor | 92.9 | 96.4 | 95.2 | 93.9 | 96.7 | 96.4 | 0 |
| wrapped | 672 | 18 | 92.0 | 97.9 | 96.1 | 93.6 | 96.7 | 96.6 | 4 |

Source books counts the distinct sample projects behind each tag. Several hard caveats come from only 1 to 3 books, and for most of them those are the only books in the whole corpus that have the caveat: JC Ryan is the only book with centered cells, Roselle the only ruled grid, Lyons and SJC the only books with NOT USED lines, and HFH, SJC and Valor the only books with struck text. A score on those tags measures how well we read those books, not the caveat in general.

## Sets

| Tag | n | Source books | Found | Status right |
| :--- | ---: | :--- | ---: | ---: |
| All | 311 | 20 | 98.4 | 75.0 |
| column_drift | 39 | 4: Forest, JC Ryan, Morris, Star | 94.9 | |
| dense_page | 103 | 9 | 97.1 | 66.7 |
| moved | 5 | 1: SJC | 60.0 | 60.0 |
| multi_page | 25 | 8 | 100.0 | |
| not_used | 11 | 2: Lyons, SJC | 100.0 | 81.8 |
| struck_page | 63 | 3: HFH, SJC, Valor | 95.2 | 66.7 |

NOT USED sets are always found. When their status is wrong it is SJC, which strikes out whole blocks under a `Not Used` header, so the struck rows make the set look non-empty. Struck-text detection should fix most of this.

## By book

| Book | n | Exact rows | qty | description | catalog | finish | mfr |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ami | 90 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| bridgeport | 109 | 89.9 | 95.4 | 100.0 | 94.5 | 100.0 | 94.5 |
| doorco | 74 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| forest | 5 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| gerrard | 166 | 94.0 | 100.0 | 94.0 | 100.0 | 100.0 | 100.0 |
| hfh | 206 | 93.2 | 98.1 | 97.1 | 93.2 | 98.5 | 98.1 |
| jcryan | 155 | 97.4 | 99.4 | 99.4 | 97.4 | 99.4 | 98.1 |
| livelle | 132 | 89.4 | 100.0 | 98.5 | 90.2 | 99.2 | 100.0 |
| lyons | 83 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| marketview | 90 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| morris | 48 | 60.4 | 100.0 | 87.5 | 60.4 | 70.8 | 100.0 |
| national | 51 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| oswego | 120 | 95.8 | 99.2 | 95.8 | 95.8 | 99.2 | 99.2 |
| roselle | 134 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| sat | 146 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| shubie | 31 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| sjc | 281 | 92.2 | 92.9 | 92.9 | 92.2 | 92.9 | 92.9 |
| star | 150 | 82.7 | 92.0 | 91.3 | 88.7 | 85.3 | 84.7 |
| usi | 10 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| valor | 137 | 97.1 | 100.0 | 97.1 | 100.0 | 100.0 | 100.0 |

## What the errors are

| Error | Where | Tag it hurts |
| :--- | :--- | :--- |
| A row with no qty and no mfr is merged into the row above | Oswego `SEALS - AS TESTED BY DOOR MANUFACTURER`, HFH `DIAGRAMS` | missing_qty |
| `As Req` qty rows are dropped | SJC hinge rows | missing_qty |
| 4-digit quantities are not read | Bridgeport `2571 Standard Hinge` | missing_qty |
| Struck rows are extracted as components | HFH, SJC, Valor | struck_page, NOT USED status |
| Columns move too far to snap, finish lands in catalog | Morris pages 233 to 263, Star page 77 | column_drift |
| Door lines read as components | Morris (27), Lyons | precision |
| Note lines attached to the last row's description | Gerrard `Interlock with D147A.`, Oswego `NOTE` | description |
| Prose catalog cells with a finish code in the mfr column | Star page 56 | full_name_mfr, the 4 swaps |
