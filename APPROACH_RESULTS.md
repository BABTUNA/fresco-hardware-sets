# Approach results

Strict scorer from [BENCHMARK.md](BENCHMARK.md), same 155 labeled pages (311 sets, 2,218 rows, 20 books). A row counts only when all five fields are exact. The held-out set is 25 pages labeled after all tuning and scored once.

| | 1. Spec per book (ours) | 2. Spec by example | 3. Per-page LLM | 4. Multimodal |
| :--- | ---: | ---: | ---: | ---: |
| Exact rows | 98.4% (2,183 / 2,218) | 97.1% (2,154 / 2,218) | 95.6% (2,121 / 2,218) | **98.9%** (2,193 / 2,218) |
| Sets fully correct | 94.5% (294 / 311) | 93.6% (291 / 311) | 81.4% (253 / 311) | **95.2%** (296 / 311) |
| Held-out rows | 97.2% (350 / 360) | 97.2% (350 / 360) | | |
| Mfr/finish swaps | 0 | 0 | 0 | 0 |
| Set numbers found, all 20 books | 99.7% (1,172 / 1,175) | 99.2% (1,166 / 1,175) | not run | not run |
| Values invented | impossible | impossible | 23 of 8,028 | 25 of 7,693 |
| LLM calls, 20 books | 22 | 39 | 694 | 694 |
| Time, 100 pages | 14 s | 32 s | 17 min | 17 min |
| Same output every run | yes | yes | no | no |

Set numbers found is the whole pipeline, not just the labeled pages: the page finder in [APPROACHES.md](APPROACHES.md#layer-1-the-page-finder) reaches all 697 set pages, approaches 1 and 2 then ran every book, and the set numbers they output are checked against every printed set header. End to end for approach 1: every set page reached, 99.7% of printed set numbers out as a set, 98.4% of rows exact on labeled pages (97.2% held out).

## Reading the numbers

- **The multimodal score is inflated.** The labels were made by Claude reading the same page images under nearly the same rules. Two independent labelers agree about 99% of the time, and approach 4 lands right there, so it is as consistent as a second labeler. Whether it is correct, this benchmark cannot say.
- **Times are half measured, half estimated.** Finder and interpreter are measured (`experiments/latency.py`: 19 s for all 14,224 pages, 0.1 s per set page). Model calls are estimated from the token counts at 1 s to first token and 60 tokens per second, one call at a time for every approach. Running 10 at once divides every column by about 10. After a spec edit, 1 and 2 rerun in seconds with no call. 3 and 4 rerun every page.
- **Approach 1 was tuned on this benchmark.** Every fix in the interpreter was found here. The held-out numbers are the ones to quote.
- **Strike-through is the dividing line.** HFH, SJC and Valor strike out revised rows. Approaches 1 and 2 detect the strike marks in the PDF and drop them, approach 4 sees them in the image, approach 3 cannot and keeps the rows.

## Where each one loses

| | Worst books | Why |
| :--- | :--- | :--- |
| 1. Spec per book | Star 72% of sets | prose cells with the finish and maker written inside a sentence |
| 2. Spec by example | Star 61% | the sample pages do not show Star's third header spelling |
| 3. Per-page LLM | Roselle 19%, Door Co 40% | values formatted differently from one call to the next |
| 4. Multimodal | Star 72% | prose cells |

## Cost

Per-call figures are from the actual test inputs and outputs.

| | 1 | 2 | 3 | 4 |
| :--- | ---: | ---: | ---: | ---: |
| Input tokens per call | 2,100 | 1,500 | 1,150 | 3,250 |
| Output tokens per call | 200 | 600 | 555 | 530 |
| Calls | 22 | 39 | 694 | 694 |

Even the most expensive approach is a few dollars for all 20 books. Determinism and editability decide this, not cost.

## Dropped approaches

| Approach | Rows | Sets |
| :--- | ---: | ---: |
| Structure labels per page, code copies the text by id | 96.2% | 77.2% |
| LLM writes a Python parser per book | 91.6% | 72.0% |
| Induce the spec, LLM on audit flags (3 of 20 books) | 80.9% | 68.5% |
| Induce the spec, no LLM | 72.5% | 52.4% |
| Camelot as the extraction layer | 20.1% | 4.5% |
| Embeddings as the page filter | 84% page recall at 66% precision, the regex finder is in [APPROACHES.md](APPROACHES.md#layer-1-the-page-finder) | |
