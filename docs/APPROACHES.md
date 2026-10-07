# Approaches

Every approach has two layers: a page finder that keeps only the pages that hold sets, then a model step on those pages. The finder is the same for all four, described below. The approaches differ in what the model does. Numbers are in [APPROACH_RESULTS.md](APPROACH_RESULTS.md).

| | What the model does | Calls for 20 books | Same output every run |
| :--- | :--- | ---: | :--- |
| **1. Spec per book (ours)** | writes a JSON layout spec from 2 sample pages | 22 | yes |
| **2. Spec by example** | points at the runs of text on 2 sample pages, code derives the spec | 39 | yes |
| **3. Grounded per-page LLM** | writes the values for every page, citing source lines | 694 | no |
| **4. Multimodal per-page LLM** | same as 3, with the page image | 694 | no |

## Layer 1: the page finder

A specbook is mostly prose. SAT TDP is 3,930 pages and 122 of them hold sets. The finder scans every page's raw text for lines shaped like a component row: a quantity, some words, then one or two short codes at the end.

```
3   EA   HINGE   5BB1 4.5 X 4.5 NRP   652   IVE
```

Two or more such lines plus hardware words (hinge, closer, lock...) make a schedule page, and consecutive ones form a run. No header wording, so it works the same on every book. SAT takes about 6 seconds.

**Does it find every set page?** A table of contents cannot say, it only gives the section. The truth is the printed set headers: a broad header pattern, independent of the finder and our output, scans every page, and a page with a set header or sitting between two of them is a set page. That gives 697 of 14,224 (`experiments/layer1_truth.py`).

| | Recall | Precision |
| :--- | ---: | ---: |
| Finder alone | 689 / 697 | 689 / 694 |
| Finder plus the expand step (header hits next to a run) | 697 / 697 | |

The 8 the finder skips have no row-shaped lines (Bridgeport door lists, a JC Ryan set that says "By Balanced Door Manufacturer", an empty Door Co set) and the expand step catches every one. The same header pattern also finds 1,175 printed set numbers and 1,172 are in our output, the 1 missing being a foodservice line that is not a set. The 21 PDFs with no hardware sets come back empty.

Embeddings and tf-idf against hint phrases were tried as the filter instead: 84% recall at 66% precision. Prose pages of a hardware section talk about the same things as the schedule. The shape of a row separates them, meaning does not.

## 1. Spec per book (ours)

Claude reads the two densest schedule pages of a book, as text with x positions, and writes a small spec: what a set header looks like, where each column sits and what it holds, how rows wrap. Plain code applies the spec to every page.

```json
{"set_header": "^HARDWARE GROUP NO\\. (?P<num>\\S+)",
 "columns": [{"field": "qty", "x": 78}, {"field": "description", "x": 146},
             {"field": "catalog", "x": 288}, {"field": "finish", "x": 462}, {"field": "mfr", "x": 506}]}
```

**Trade-off.** One call per book, deterministic after that, and a spec edit fixes every set in the book. The fragile part is the regex: every one-shot failure was a header the model's pattern did not match (an anchored start, a plural form, a space in the number). An audit catches most of these and triggers one repair call.

**Why only 2 sample pages.** Tested against 4 densest pages and against up to 4 pages picked for variety (new header spellings and line shapes), 34 fresh one-shot specs, no repair call. Rows: 96.3% with 2 pages, 96.0% with 4, 95.9% with the variety pick. The 4 densest pages look like the first 2, so nothing is learned. The variety pick found Star's second header spelling (59% to 71% of rows) and broke Marketview (100% to 71%): the writer saw door lists on the extra pages and wrote a `set_meta` pattern loose enough to swallow component rows. HFH misses the same rows in all three. The sample is not the weak point, the regex is, and the audit plus one repair call (96.3% to 98.4%) is worth more than any page selection. `experiments/sample_pages.py`, specs in `experiments/specs_sample/`.

## 2. Spec by example

Every run of words on the 2 sample pages gets an id. The model only points: which ids form a row, which field each id is, which line is a header. Code derives the spec from those labels (columns from where the labeled runs sit, the header pattern generalized from the labeled header lines) and the same interpreter runs it over every page.

```
L6: [14@80]6 [15@112]EA [16@148]HINGE [17@290]5BB1HW 4.5 X 4.5 - NRP AT [18@464]652 [19@508]IVE
L7: [20@290]OUTSWINGING DRS
```
```json
{"qty": [14], "description": [16], "catalog": [17, 20], "finish": [18], "mfr": [19]}
```

**Trade-off.** Approach 1 with the fragile part removed. The model never writes a regex or a value, so there is far less to vary between runs, and it scores within a point of approach 1. It only knows what the two sample pages show.

## 3. Grounded per-page LLM

Every page goes to the model as numbered lines. The model writes the sets and rows, and each row cites the lines it came from. Code checks the citations and builds the boxes. This is how most production extraction products work.

**Trade-off.** Handles any layout with no rules, but one call per page, values can drift between runs (`613` against `613 (OIL RUBBED BRONZE)`), and 23 of 8,028 values were not in the lines they cited.

## 4. Multimodal per-page LLM

Approach 3 plus the rendered page image. The model uses the image for layout and strike-through, and copies values from the text lines.

**Trade-off.** The only approach that sees struck-through revisions, and the best raw score. Twice the tokens of 3, and the labels were made by Claude from the same images under the same rules, so its score is the most inflated.

## Tested and dropped

| Approach | Result | Why |
| :--- | :--- | :--- |
| Structure labels per page: the model points at runs on every page, code copies the text | 96.2% rows, 77.2% sets | nothing can be invented, but one call per page, cannot see strike-through, and approach 2 gets the same guarantee in 39 calls |
| LLM writes a Python parser per book | 91.6% rows | breaks on layouts the sample pages did not show, generated code cannot be edited in a UI |
| Induce the spec from repetition, no LLM | 72.5% rows | headers and columns that few rows share give it nothing to count |
| Induce, LLM only on audit flags | 80.9% rows | the audit was built for LLM spec failures and let the induction failures through |
| Embeddings or tf-idf as the page filter | 84% page recall at 66% precision | prose pages talk about the same things as the schedule, row shapes separate them |
| Open source table parsers (Camelot, pdfplumber, PyMuPDF, img2table, gmft, Docling) | at most 67.8% clean rows, 20.1% as a pipeline | wrapped cells split, whitespace lists are not detected as tables |

## Code

| Approach | Where |
| :--- | :--- |
| finder | `experiments/finder.py`, `layer1_truth.py` |
| 1 | `experiments/e2e.py`, `spec_parse.py`, `specs_e2e/` |
| 2 | `experiments/alt_byexample.py`, `alt_struct/PROMPT.md` |
| 3 | `experiments/alt_llm/PROMPT.md`, `alt_llm/convert.py` |
| 4 | `experiments/alt_mm/PROMPT.md` |
| dropped | `alt_struct/convert.py`, `alt_code/`, `alt_induce2.py`, `layer1_eval.py`, `alt_camelot.py`, `alt_docling_ceiling.py` |
