# Approach results

Strict scorer from [BENCHMARK.md](BENCHMARK.md), same 155 labeled pages (311 sets, 2,218 rows, 20 books). A row counts only when all five fields are exact. The held-out set is 25 pages labeled after all tuning and scored once.

| | 1. Spec per book (ours) | 2. Spec by example | 3. Per-page LLM | 4. Multimodal |
| :--- | ---: | ---: | ---: | ---: |
| Exact rows | 98.5% (2,184 / 2,218) | 97.1% (2,154 / 2,218) | 95.6% (2,121 / 2,218) | **98.9%** (2,193 / 2,218) |
| Sets fully correct | 94.9% (295 / 311) | 93.6% (291 / 311) | 81.4% (253 / 311) | **95.2%** (296 / 311) |
| Held-out rows | 97.2% (350 / 360) | 97.2% (350 / 360) | | |
| Mfr/finish swaps | 0 | 0 | 0 | 0 |
| Set numbers found, all 20 books | 99.9% (1,174 / 1,175) | 99.2% (1,166 / 1,175) | not run | not run |
| Set pages read, all 20 books | 697 / 697 | 697 / 697 | not run | not run |
| Rows extracted, all 20 books, unscored | 10,312 | 10,328 | not run | not run |
| Values invented | impossible | impossible | 23 of 8,028 | 25 of 7,693 |
| LLM calls, 20 books | 20 + repairs (2 in the last run) | 39 | 694 | 694 |
| Time, 100 pages | 14 to 45 s | 32 s | 17 min | 17 min |
| Same output every run | yes | yes | no | no |
| Cost, 20 books (per set page) | $0.21 ($0.0003) | $0.53 ($0.0008) | $8.20 ($0.012) | $12.30 ($0.018) |

Notes:

- The first rows score the 155 labeled pages (311 sets, 2,218 labeled rows, about a fifth of the set pages). The "all 20 books" rows are the whole run: 697 set pages read and about 10,300 rows extracted. Those rows have no labels, so the only check possible there is the set numbers, against an independent scan of the printed headers.
- The multimodal score is inflated: the labels were made by Claude from the same page images.
- Approach 1 was tuned on this benchmark. Quote the held-out row.
- Times: finder and interpreter measured. Approach 1's model call measured on the 20 fresh compiles, 4 to 35 s per book (one call, two where the audit fired). Calls for approaches 2 to 4 estimated from token counts at 60 tokens per second, one call at a time.
- Cost from the measured tokens per call at $3 per million input and $15 per million output.

## Random samples

The 155 pages above were partly picked to hit caveats. These two sets were drawn at random, so they say what a typical page looks like. Round 1 is 2 random schedule pages per book, labeled first and used in tuning. The held-out set was labeled after all tuning and scored once (`PAGES=eval/round1_pages.json python bench.py`, `GT=eval/holdout/gt python bench.py`).

| | 1. Spec per book (ours) | 2. Spec by example | 3. Per-page LLM | 4. Multimodal |
| :--- | ---: | ---: | ---: | ---: |
| Round 1, 39 random pages: exact rows | 99.6% (531 / 533) | 99.6% (531 / 533) | 96.2% (513 / 533) | 99.1% (528 / 533) |
| Round 1: sets fully correct | 98.5% (66 / 67) | 97.0% (65 / 67) | 73.1% (49 / 67) | 92.5% (62 / 67) |
| Held-out, 25 random pages: exact rows | 97.2% (350 / 360) | 97.2% (350 / 360) | not run | not run |
| Held-out: sets fully correct | 89.5% (34 / 38) | 89.5% (34 / 38) | not run | not run |

## Where each one loses

| | Worst books | Why |
| :--- | :--- | :--- |
| 1. Spec per book | Star 72% (13 / 18 sets) | prose cells with the finish and maker written inside a sentence |
| 2. Spec by example | Star 61% (11 / 18) | the sample pages do not show Star's third header spelling |
| 3. Per-page LLM | Roselle 19% (4 / 21), Door Co 40% (2 / 5) | values formatted differently from one call to the next |
| 4. Multimodal | Bridgeport 65% (11 / 17), Star 72% (13 / 18) | maker left inside the catalog cell (`HORTON 4100 LH PULL SERIES`), prose cells |

## Dropped approaches

| Approach | Rows | Sets |
| :--- | ---: | ---: |
| Structure labels per page, code copies the text by id | 96.2% | 77.2% |
| LLM writes a Python parser per book | 91.6% | 72.0% |
| Induce the spec, LLM on audit flags (3 of 20 books) | 80.9% | 68.5% |
| Induce the spec, no LLM | 72.5% | 52.4% |
| Camelot as the extraction layer | 20.1% | 4.5% |
| Embeddings as the page filter | 84% page recall at 66% precision, the regex finder is in [APPROACHES.md](APPROACHES.md#layer-1-the-page-finder) | |
