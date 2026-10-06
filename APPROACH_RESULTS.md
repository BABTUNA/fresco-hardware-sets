# Approach results

All four approaches in [APPROACHES.md](APPROACHES.md) were scored with the strict scorer from [BENCHMARK.md](BENCHMARK.md) on the same 155 labeled pages: 311 sets, 2,218 rows, 20 books. A row only counts if qty, description, catalog, finish and mfr are all right. Approach 1 is scored after the interpreter fixes of 2026-10-05 and 2026-10-06. The other three are unchanged since their test runs.

## Summary

| | 1. Spec per book (ours) | 2. Per-page LLM | 3. Multimodal per-page | 4. Parser per book |
| :--- | ---: | ---: | ---: | ---: |
| Exact rows | 98.4% | 95.8% | **99.1%** | 91.6% |
| Exact rows, pages the spec writer never saw | 98.3% | 95.8% | 99.0% | 90.9% |
| Precision | 98.6% | 91.9% | **99.1%** | 88.8% |
| Per-book average | 98.8% | 96.3% | 99.2% | 92.5% |
| Sets fully correct | 94.5% | 82.6% | **96.5%** | 72.0% |
| Sets found | 99.4% | 99.7% | 99.7% | 96.8% |
| NOT USED and moved status right | 93.8% | 87.5% | 100.0% | 50.0% |
| Mfr/finish swaps | 0 | 0 | 0 | 0 |
| LLM calls for 20 books | 22 | 694 | 694 | 20 |
| Tokens for 20 books, estimated | ~51K | ~1.2M | ~2.6M | ~87K |
| Same output every run | yes | no | no | yes |

**Before reading the multimodal number.** The labels were made by Claude reading the same page images under nearly the same rules. Two independent labelers agree with each other about 99% of the time, and approach 3 lands right there. So 99.1% shows it is as consistent as a second labeler. Whether that means correct, this benchmark cannot tell. A small set of labels made by hand would separate the two.

## By tier

| Tier | n | Ours | Per-page | Multimodal | Parser |
| :--- | ---: | ---: | ---: | ---: | ---: |
| T0 trivial | 459 | 100.0 | 100.0 | 99.6 | 97.6 |
| T1 one caveat | 669 | 100.0 | 99.4 | 100.0 | 98.2 |
| T2 hard | 1,090 | 96.8 | 91.8 | 98.3 | 85.0 |

## By caveat

Exact rows on rows with each tag.

| Tag | n | Ours | Per-page | Multimodal | Parser |
| :--- | ---: | ---: | ---: | ---: | ---: |
| missing_qty | 107 | 95.3 | 91.6 | 98.1 | 68.2 |
| column_drift | 262 | 93.1 | 95.0 | 94.7 | 62.6 |
| struck_page | 392 | 97.4 | 96.9 | 99.7 | 96.7 |
| ambiguous_code | 548 | 98.4 | 98.7 | 98.4 | 89.1 |
| wrapped | 672 | 96.0 | 92.6 | 97.6 | 86.6 |
| multi_page | 291 | 96.6 | 96.6 | 99.3 | 91.4 |

## By book

Exact rows.

| Book | n | Ours | Per-page | Multimodal | Parser |
| :--- | ---: | ---: | ---: | ---: | ---: |
| ami | 90 | 100.0 | 100.0 | 100.0 | 100.0 |
| bridgeport | 109 | 100.0 | 100.0 | 98.2 | 89.9 |
| doorco | 74 | 100.0 | 82.4 | 100.0 | 91.9 |
| forest | 5 | 100.0 | 100.0 | 100.0 | 100.0 |
| gerrard | 166 | 100.0 | 98.8 | 98.8 | 98.8 |
| hfh | 206 | 95.1 | 95.6 | 99.0 | 95.1 |
| jcryan | 155 | 96.8 | 100.0 | 100.0 | 70.3 |
| livelle | 132 | 98.5 | 100.0 | 100.0 | 98.5 |
| lyons | 83 | 100.0 | 100.0 | 100.0 | 100.0 |
| marketview | 90 | 100.0 | 100.0 | 100.0 | 100.0 |
| morris | 48 | 97.9 | 97.9 | 97.9 | 70.8 |
| national | 51 | 100.0 | 100.0 | 100.0 | 100.0 |
| oswego | 120 | 99.2 | 100.0 | 100.0 | 95.8 |
| roselle | 134 | 100.0 | 64.2 | 100.0 | 93.3 |
| sat | 146 | 100.0 | 100.0 | 100.0 | 100.0 |
| shubie | 31 | 100.0 | 100.0 | 100.0 | 100.0 |
| sjc | 281 | 100.0 | 99.3 | 100.0 | 99.3 |
| star | 150 | 90.7 | 90.7 | 90.7 | 49.3 |
| usi | 10 | 100.0 | 100.0 | 100.0 | 100.0 |
| valor | 137 | 98.5 | 97.1 | 100.0 | 97.1 |

## What each approach gets wrong

**1. Spec per book.** After the fixes, most of its misses are Star's prose catalog cells, Bridgeport's `IVES 69 / 63` (the label splits the maker out, we keep it in the catalog), and a few wrapped lines in centered-cell books attached to the wrong row. Before the fixes it lost 101 rows to four spec-language gaps: rows with no qty and no mfr, columns that moved too far to snap, 4-digit quantities, and note lines glued to the row above.

**2. Per-page LLM.** Before our fixes it got 101 rows right that we missed, all in those four gaps. We get 65 rows right that it misses, and 61 of those are Roselle and Door Co, where it formatted values inconsistently between runs. One batch wrote Roselle's finish as `613`, the others as `613 (OIL RUBBED BRONZE)`.

**3. Multimodal per-page.** Its only weak book is Star (90.7%), whose catalog cells are full sentences with the finish and maker written inside them.

**4. Parser per book.** Before our fixes it beat ours on SJC (99.3% vs 92.2%) and Livelle, where code could say more than the spec language. It falls apart on layouts the two sample pages did not show: Star (49.3%), JC Ryan's centered cells (70.3%) and Morris's second layout (70.8%).

## The model points, code copies (2026-10-06)

Same scorer, same 155 pages.

| | 1. Ours (LLM writes spec) | 8. Spec by example | 7. Structure labels per page | 2. Per-page LLM writes values |
| :--- | ---: | ---: | ---: | ---: |
| Exact rows | 98.4% | 97.1% | 96.2% | 95.8% |
| Sets fully correct | 94.5% | 93.6% | 77.2% | 82.6% |
| Precision | 98.6% | 97.2% | 91.5% | 91.9% |
| Mfr/finish swaps | 0 | 0 | 0 | 0 |
| Values invented | none possible | none possible | none possible | 23 of 8,028 not in cited lines |
| Held-out set, rows | 97.2% | 97.2% | | |
| Held-out set, sets | 89.5% | 89.5% | | |
| LLM calls for 20 books | 22 | 20 | 694 | 694 |
| Model output | a regex spec | run ids for 2 pages | run ids per page | field values per page |

Approach 7 referenced 10,856 run ids across the 155 pages, all of them on the page. Its sets number is low for the same reason as approach 2: it cannot see strike-through, so SJC and HFH keep struck rows (SJC 59% of sets), and two conventions (Roselle's set-column text folded into descriptions, Bridgeport's inline maker) cost the rest.

Approach 8 reaches 100% of sets on 11 books. Its misses are Star (61%), where the sample pages do not show the third header spelling, and the same ragged wraps that limit approach 1 (HFH, Morris, JC Ryan at 86 to 88%). It scored 89.5% of sets on the held-out pages against approach 1's 89.5%.

## Two-layer variants (2026-10-06)

Same scorer, same 155 pages. Approach 1 is shown after its fixes.

| | 1. Ours | 5. Deterministic induction | 6. Induce, LLM on flags | 4. Parser per book |
| :--- | ---: | ---: | ---: | ---: |
| Exact rows | 98.4% | 72.5% | 80.9% | 91.6% |
| Sets fully correct | 94.5% | 52.4% | 68.5% | 72.0% |
| Precision | 98.6% | 70.9% | 80.1% | 88.8% |
| Sets found | 99.4% | 89.1% | 91.6% | 96.8% |
| Mfr/finish swaps | 0 | 0 | 0 | 0 |
| LLM calls for 20 books | 22 | 0 | 3 | 20 |

Approach 5 gets 10 of 20 books to 89% or better of sets fully correct and 0% on five (Forest, Morris, Valor, and nearly so on JC Ryan and Bridgeport), where a column was never found or the header prefix chosen was a row. Approach 6 recovers SJC, Star and Door Co, the three books the audit flagged, and inherits the rest.

### Layer 1: which pages hold sets

Truth is the 700 pages (of 14,224) on which the pipeline placed a set or a row. Finder is a fixed decision. The other two get the global threshold that maximizes their own F1, which is generous to them.

| Method | Page recall | Precision | Pages passed to layer 2 |
| :--- | ---: | ---: | ---: |
| Regex finder (ours) | 98.9% | 99.7% | 694 |
| tf-idf vs hint phrases, best F1 | 85.7% | 70.6% | 850 |
| tf-idf, 95% recall | 95.0% | 54.6% | 1,217 |
| MiniLM embeddings vs hint phrases, best F1 | 84.0% | 66.4% | 885 |
| MiniLM embeddings, 95% recall | 95.0% | 55.8% | 1,191 |

### Spec variance

Two fresh rewrites (A and B) of the specs for Oswego, Gerrard, SJC and JC Ryan.

| Book | Spec keys that differ from the original | Rows and sets extracted | Score |
| :--- | :--- | :--- | :--- |
| Oswego | set_header, set_meta, skip, end (A only) | identical | identical |
| Gerrard | set_header, skip, end (A only) | identical | identical |
| SJC | set_header, skip, end (A only) | identical | identical |
| JC Ryan | skip, and set_header and end (A only) | identical | identical |

## Grounding

For the two per-page approaches, every value was checked against the lines it cited.

| Approach | Values found in their cited lines |
| :--- | ---: |
| Per-page LLM | 8,005 of 8,028 (99.7%) |
| Multimodal per-page | 7,668 of 7,693 (99.7%) |

Neither approach invents values. Their errors are values put in the wrong field or rows split or merged differently.

## Cost

| | Ours | Per-page | Multimodal | Parser |
| :--- | ---: | ---: | ---: | ---: |
| Input tokens per call | ~2,100 | ~1,150 | ~3,250 | ~1,800 |
| Output tokens per call | ~200 | ~555 | ~530 | ~2,500 |
| Calls for 20 books | 22 | 694 | 694 | 20 |
| Total tokens, estimated | ~51K | ~1.2M | ~2.6M | ~87K |

Per-call numbers come from the actual inputs and outputs of the test runs. The multimodal input adds about 2,100 tokens for a 1105 by 1430 page image. Even the most expensive approach is a few million tokens for all 20 books, so cost alone does not decide this. Determinism and editability matter more.

## Ruled-out approaches

**Open source table libraries.** Clean-row ceiling: the share of labeled rows a library returns as one table row with the catalog, finish and mfr each sitting alone in a cell, after merging rows that have no qty into the row above. This is the best any column mapper on top of the library could reach.

| Library | Ceiling |
| :--- | ---: |
| Camelot 2.0, hybrid | 67.8% |
| Camelot 2.0, stream | 66.2% |
| pdfplumber, text strategy | 51.2% |
| PyMuPDF, text strategy | 51.2% |
| Camelot 2.0, network | 47.2% |
| img2table, borderless | 41.8% |
| Docling 2.133 | 32.8% |
| gmft | 31.1% |

Docling found a table on only 64 of 155 pages. Its open issue #3749 says whitespace-aligned tables are read as body text.

**No-LLM template induction.** 25.3% exact rows, 41.8% precision. Column roles came out right in most books. Set headers came out wrong in about half, so their rows landed in the wrong sets.

**Spec by default, per-page LLM on risky pages.** 94.3% exact rows. The trigger (any blank qty or empty description) sent 73 of 155 pages to the LLM, including Roselle and Door Co, where the spec was already better.

## Reading these results

- **The labels favor the per-page approaches.** They were made by Claude with the same field rules those prompts use, so formatting choices line up. The effect is strongest for the multimodal approach.
- **Our interpreter was tuned on this corpus.** Approach 4 got one shot with no repair, and approach 1 had several rounds of fixes.
- **Ours now scores above the text-only per-page LLM** on rows (98.0% vs 95.8%) and sets (92.0% vs 82.6%), after fixing the four gaps the per-page comparison exposed. Those fixes were made against this benchmark, so the per-page numbers are the more conservative reading.
- **The multimodal approach is the strongest result.** It is also the least certain one, until some pages are labeled by hand.
