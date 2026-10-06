# Approach results

Strict scorer from [BENCHMARK.md](BENCHMARK.md), same 155 labeled pages (311 sets, 2,218 rows, 20 books). A row counts only when all five fields are exact. The held-out set is 25 pages labeled after all tuning and scored once.

| | 1. Spec per book (ours) | 2. Spec by example | 3. Per-page LLM | 4. Multimodal |
| :--- | ---: | ---: | ---: | ---: |
| Exact rows | 98.4% | 97.1% | 95.8% | **99.1%** |
| Sets fully correct | 94.5% | 93.6% | 82.6% | **96.5%** |
| Precision | 98.6% | 97.2% | 91.9% | **99.1%** |
| Mfr/finish swaps | 0 | 0 | 0 | 0 |
| Held-out rows | 97.2% | 97.2% | | |
| Held-out sets | 89.5% | 89.5% | | |
| Values invented | impossible | impossible | 23 of 8,028 | 25 of 7,693 |
| LLM calls, 20 books | 22 | 39 | 694 | 694 |
| Tokens, estimated | 51K | 82K | 1.2M | 2.6M |
| Same output every run | yes | yes | no | no |
| Set pages reached, all 20 books | 697 / 697 | 697 / 697 | 697 / 697 | 697 / 697 |
| Printed set numbers found, all 20 books | 1,172 / 1,175 | 1,166 / 1,175 | not run whole-book | not run whole-book |

The last two rows are the whole pipeline, not just the labeled pages. Every approach shares the page finder in [APPROACHES.md](APPROACHES.md#layer-1-the-page-finder), which reaches all 697 set pages. Approaches 1 and 2 then ran every book, and the set numbers they output are checked against every printed set header. End to end for approach 1: every set page reached, 99.7% of printed set numbers out as a set, 98.4% of rows exact on labeled pages (97.2% held out).

## Reading the numbers

- **The multimodal score is inflated.** The labels were made by Claude reading the same page images under nearly the same rules. Two independent labelers agree about 99% of the time, and approach 4 lands right there, so it is as consistent as a second labeler. Whether it is correct, this benchmark cannot say.
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

## Latency

Measured (`experiments/latency.py`): the finder reads all 14,224 pages of the 20 books in 19 s, the interpreter runs the 703 set pages in 59 s. SAT, the largest book (3,930 pages, 122 of them sets), takes 5.5 s to find and 11.7 s to parse. Rendering a page image for approach 4 is 0.13 s.

Modeled: the model calls in these experiments were not made through the API, so their time comes from the measured token counts at 1 s to first token and 60 output tokens per second, a Sonnet-class rate. That gives 4 s per call for approach 1, 11 s for 2, 10 s for 3 and 4. Approaches 3 and 4 are also shown with 10 calls in flight, a common rate limit.

| | 1. Spec per book | 2. Spec by example | 3. Per-page LLM | 4. Multimodal |
| :--- | ---: | ---: | ---: | ---: |
| Oswego, 28 set pages | 7 s | 25 s | 4.8 min, 30 s at 10 in flight | 4.7 min, 32 s |
| SAT, 122 set pages | 22 s | 39 s | 21 min, 2.2 min | 20 min, 2.4 min |
| All 20 books, 694 calls for 3 and 4 | 3 min | 8.5 min | 2 h, 12 min | 1.9 h, 13 min |
| After a spec edit | interpreter only: 2 s, 12 s for SAT | same | every page again | every page again |

The gap is structural. Approaches 1 and 2 make a fixed number of calls per book and the rest is local code, so a book takes seconds whatever its size. Approaches 3 and 4 make one call per page, so their time grows with the book and a correction means paying for the whole book again.

## Dropped approaches

| Approach | Rows | Sets |
| :--- | ---: | ---: |
| Structure labels per page, code copies the text by id | 96.2% | 77.2% |
| LLM writes a Python parser per book | 91.6% | 72.0% |
| Induce the spec, LLM on audit flags (3 of 20 books) | 80.9% | 68.5% |
| Induce the spec, no LLM | 72.5% | 52.4% |
| Camelot as the extraction layer | 20.1% | 4.5% |
| Embeddings as the page filter | 84% page recall at 66% precision, the regex finder is in [APPROACHES.md](APPROACHES.md#layer-1-the-page-finder) | |
