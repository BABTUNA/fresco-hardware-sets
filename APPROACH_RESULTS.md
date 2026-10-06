# Approach results

Strict scorer from [BENCHMARK.md](BENCHMARK.md), same 155 labeled pages (311 sets, 2,218 rows, 20 books). A row counts only when all five fields are exact. The held-out set is 25 pages labeled after all tuning and scored once.

| | 1. Spec per book (ours) | 2. Spec by example | 3. Structure labels | 4. Per-page LLM | 5. Multimodal |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Exact rows | 98.4% | 97.1% | 96.2% | 95.8% | **99.1%** |
| Sets fully correct | 94.5% | 93.6% | 77.2% | 82.6% | **96.5%** |
| Precision | 98.6% | 97.2% | 91.5% | 91.9% | **99.1%** |
| Mfr/finish swaps | 0 | 0 | 0 | 0 | 0 |
| Held-out rows | 97.2% | 97.2% | | | |
| Held-out sets | 89.5% | 89.5% | | | |
| Values invented | impossible | impossible | impossible | 23 of 8,028 | 25 of 7,693 |
| LLM calls, 20 books | 22 | 39 | 694 | 694 | 694 |
| Tokens, estimated | 51K | 82K | 1.3M | 1.2M | 2.6M |
| Same output every run | yes | yes | no | no | no |

## Reading the numbers

- **The multimodal score is inflated.** The labels were made by Claude reading the same page images under nearly the same rules. Two independent labelers agree about 99% of the time, and approach 5 lands right there, so it is as consistent as a second labeler. Whether it is correct, this benchmark cannot say.
- **Approach 1 was tuned on this benchmark.** Every fix in the interpreter was found here. The held-out numbers are the ones to quote.
- **Strike-through is the dividing line.** HFH, SJC and Valor strike out revised rows. Approaches 1 and 2 detect the strike marks in the PDF and drop them, approach 5 sees them in the image, approaches 3 and 4 cannot and keep the rows. That is most of the gap between 96% rows and 77% sets for approach 3.

## Where each one loses

| | Worst books | Why |
| :--- | :--- | :--- |
| 1. Spec per book | Star 72% of sets | prose cells with the finish and maker written inside a sentence |
| 2. Spec by example | Star 61% | the sample pages do not show Star's third header spelling |
| 3. Structure labels | SJC 59%, Roselle 29% | struck rows kept, set-column text folded into descriptions |
| 4. Per-page LLM | Roselle 19%, Door Co 40% | values formatted differently from one call to the next |
| 5. Multimodal | Star 72% | prose cells |

## Cost

Per-call figures are from the actual test inputs and outputs.

| | 1 | 2 | 3 | 4 | 5 |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Input tokens per call | 2,100 | 1,500 | 1,360 | 1,150 | 3,250 |
| Output tokens per call | 200 | 600 | 530 | 555 | 530 |
| Calls | 22 | 39 | 694 | 694 | 694 |

Even the most expensive approach is a few dollars for all 20 books. Determinism and editability decide this, not cost.

## Dropped approaches

| Approach | Rows | Sets |
| :--- | ---: | ---: |
| LLM writes a Python parser per book | 91.6% | 72.0% |
| Induce the spec, LLM on audit flags (3 of 20 books) | 80.9% | 68.5% |
| Induce the spec, no LLM | 72.5% | 52.4% |
| Camelot as the extraction layer | 20.1% | 4.5% |
| Embeddings as the page filter | 84% page recall at 66% precision, the regex finder is in [APPROACHES.md](APPROACHES.md#layer-1-the-page-finder) | |
