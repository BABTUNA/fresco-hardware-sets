# Approaches

Four approaches made the cut. Each one was run on the same 155 labeled pages and scored with the same strict scorer. The numbers are in [APPROACH_RESULTS.md](APPROACH_RESULTS.md).

| Approach | One line | LLM calls for 20 books |
| :--- | :--- | ---: |
| **1. Spec per book (ours)** | An LLM writes a small layout spec once per book, plain code reads every page with it | 22 |
| **2. Grounded per-page LLM** | An LLM reads every page and cites the lines each value came from | 694 |
| **3. Multimodal per-page LLM** | Same as 2, plus the page image for layout and strike-through | 694 |
| **4. Parser per book** | An LLM writes a Python parser once per book | 20 |

The 694 is the number of schedule pages across the 20 books.

## 1. Spec per book (ours)

**What it does.** Claude reads the two densest schedule pages of a book, as text with x positions, and writes a JSON spec. Code then applies that spec to every page. Oswego's spec, shortened:

```json
{"set_header": "^HARDWARE GROUP NO\\. (?P<num>\\S+)",
 "columns": [{"field": "qty", "x": 78}, {"field": "description", "x": 146},
             {"field": "catalog", "x": 288}, {"field": "finish", "x": 462}, {"field": "mfr", "x": 506}]}
```

**Why it is a serious option.** One LLM call per book, the same output on every run, and a fix to the spec fixes every set in the book. Evaporate (VLDB 2024) and Scout (arXiv 2608.08261, Aug 2026) both show that an LLM writing an extractor once can match direct LLM extraction at a fraction of the cost.

**Where it is weak.** The spec language only says what its 9 keys can say, so everything else has to be a general rule in the interpreter. Rows with no qty, struck text, note lines and column drift all started out as misses and were fixed as interpreter rules. What is left is prose-style cells, where the finish and maker are written inside a sentence (Star).

**How it was tested.** The spec was written from the two densest pages of each book. An audit then checked the output against the whole book, and the 2 books it flagged got one repair call. The interpreter was improved over several rounds on this corpus, so this approach had more tuning than the others.

## 2. Grounded per-page LLM

**What it does.** Every page goes to the model as numbered lines with x positions. The model returns the sets, and every row cites its source lines.

```
L12 [80]6 [112]EA [148]HINGE [290]5BB1HW 4.5 X 4.5 NRP [464]652 [508]IVE
```

```json
{"qty": 6, "description": "HINGE", "catalog": "5BB1HW 4.5 X 4.5 NRP", "finish": "652", "mfr": "IVE", "lines": [12]}
```

Code checks that each value appears in the lines it cites, and builds the bounding box from those lines.

**Why it is a serious option.** It is how most production "AI extraction plus review" products work. Claude citations, LandingAI's chunk references and Google's open source LangExtract all ground values this way. The model handles wrapped rows, blank quantities and odd layouts without any rules.

**Where it is weak.** One call per page, output that can change between runs, and it cannot see strike-through from text alone.

**How it was tested.** 10 Claude subagents, about 16 pages each, with the same field rules the labelers used.

## 3. Multimodal per-page LLM

**What it does.** Approach 2 plus the rendered page image. The model uses the image to see which lines form one row, which column a value sits in, and which rows are struck through. It copies every value from the numbered text lines, never from the image, and cites them.

**Why it is a serious option.** It is the only approach that sees struck-through revisions, which are on 52 HFH pages, 31 SJC pages and 7 Valor pages. Reading values from the text layer keeps codes exact. Image-only reading turned `SI6X` into `SR64` during labeling.

**Where it is weak.** The same cost and variability as approach 2, plus an image per page, about twice the tokens.

**How it was tested.** The same 10 batches as approach 2, with the page image added.

## 4. Parser per book

**What it does.** Claude reads the same two-page sample as approach 1 and writes a Python function for the book:

```python
def parse(pages):
    # pages: [{"page": 417, "lines": [{"text", "x0", "x1", "top", "bottom", "words": [...]}]}]
    ...
    return sets
```

The function runs in a sandbox over every schedule page.

**Why it is a serious option.** It keeps approach 1's cost and determinism, but code can express anything a spec cannot, like door lines, notes or `As Req` quantities. Evaporate-Code+ and Scout write extraction code the same way.

**Where it is weak.** Generated code has to be sandboxed, cannot be edited in a UI the way a spec can, and only knows the layouts its two sample pages showed.

**How it was tested.** One shot per book, no repair. Each parser had a 5 minute limit.

## Two-layer variants tested on 2026-10-06

Every approach above already has two layers: a page filter, then extraction on the filtered pages. This round swapped each layer for something else and kept what measured well. Numbers in [APPROACH_RESULTS.md](APPROACH_RESULTS.md).

### 5. Deterministic spec induction, no LLM

**What it does.** Same layer 1 (the regex page finder) and the same interpreter as approach 1, but the spec is induced from the book itself instead of written by Claude. Column positions come from where rows align, column roles from what each column holds (finish-shaped codes, maker codes, unit words), and the set header from the line shape that repeats with a distinct id and is followed by rows. Running headers and footers are the shapes that repeat on most pages at the same height.

**Why it is a serious option.** No LLM call at all, so the compile step is as deterministic as the rest. It answers the objection that a model-written spec can come out differently on another run.

**Where it is weak.** It only sees repetition. A header shape with one odd spelling, a column that few rows use, or a book with one set gives it nothing to count. 72.5% of rows and 52.4% of sets.

**Code.** `experiments/alt_induce2.py`.

### 6. Induce first, LLM only on audit flags

**What it does.** Approach 5, then the audit from approach 1 runs on the result. A book the audit flags gets the LLM-written spec instead. The LLM touches only books where the deterministic spec visibly failed.

**Why it is a serious option.** It is a dial between 5 and 1: fewer calls and more determinism, at the accuracy the audit can protect. On this corpus 3 of 20 books went to the LLM.

**Where it is weak.** The audit was built to catch the ways LLM specs fail (a header variant missed, columns swapped), not the ways induction fails (a column never found, a header prefix that is really a row). It let four badly induced books through. A stricter trigger would send more books to the LLM and move the number toward approach 1.

**Code.** The audit in `experiments/e2e.py` over the output of `alt_induce2.py`.

### Tested and dropped this round

| Variant | Result | Why it is out |
| :--- | :--- | :--- |
| **Embeddings as layer 1** (MiniLM, and tf-idf, ranking every page against hint phrases) | 84% page recall at 66% precision, and about 1,190 pages passed to reach 95% recall | The regex finder gets 98.9% recall at 99.7% precision passing 694 pages. Prose pages of a hardware section talk about the same things as the schedule, so meaning does not separate them. Row shapes do. |
| **Camelot as layer 2** (hybrid mode rows on the finder's pages, roles from value statistics, sets from the induced header) | 20.1% of rows, 4.5% of sets, 28 swaps | Overlapping tables repeat rows, wrapped cells land in separate rows with their own first cell, and the column split changes from page to page. Its clean-row ceiling of 67.8% was never reachable in practice. |

### On the nondeterminism of writing the spec

Two fresh writers rewrote the specs for Oswego, Gerrard, SJC and JC Ryan from the same sample pages. Every rewrite differed from the original in regex wording (the header pattern, the skip list, the end marker), and all three versions extract identical output: the same sets, the same rows, the same scores. The spec is a small constrained artifact and the interpreter normalizes the phrasing. In the build the spec is also written once per book and saved, so every run after compile is deterministic by construction.

## Ruled out

| Approach | Result | Why it is out |
| :--- | :--- | :--- |
| **Open source table libraries**: Camelot, pdfplumber, PyMuPDF, img2table, gmft, Docling | At most 67.8% of rows come out as one clean table row | Wrapped cells split into extra rows, and whitespace lists are often not detected as tables. That is before any column mapping. A full pipeline on the best one (Camelot) reached 20% of rows, see above. |
| **No-LLM template induction, first attempt** | 25.3% exact rows | Its running-header filter dropped every row shape that repeats across pages, which is most component rows. Fixed in approach 5 above. |
| **Spec by default, per-page LLM on pages with a blank qty** | 94.3% exact rows | The trigger sent 47% of pages to the LLM, including pages the spec already got right. It needs a better trigger. |

## Code

| Approach | Where |
| :--- | :--- |
| 1 | `experiments/e2e.py`, `spec_parse.py`, `specs_e2e/` |
| 2 | `experiments/alt_llm/PROMPT.md`, `alt_llm/convert.py` |
| 5 | `experiments/alt_induce2.py` |
| 6 | `experiments/alt_induce2.py` plus the audit in `e2e.py` |
| Layer 1 comparison | `experiments/layer1_score.py`, `layer1_eval.py` |
| Camelot layer 2 | `experiments/alt_camelot.py` |
| 3 | `experiments/alt_mm/PROMPT.md`, `alt_llm/convert.py` |
| 4 | `experiments/alt_code/PROMPT.md`, `alt_code/run.py`, `alt_code/parsers/` |
| No-LLM induction | `experiments/alt_induce.py` |
| Library ceilings | `experiments/alt_docling_ceiling.py` |
