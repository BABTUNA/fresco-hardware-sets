# fresco-hardware-sets

Extracts door hardware sets from Division 08 spec PDFs for the Fresco take-home. `hwsets/` is the extractor, `app/` the viewer, `experiments/` the research and the benchmark, `docs/` the write-ups.

## The idea

A model reads two schedule pages of a book once and writes a short layout spec. Plain code then reads every page with it. One call per book, deterministic after that, and every value comes from real words on the page, so each set and row carries a page and a bounding box.

Oswego's spec, shortened:

```json
{
  "set_header": "^HARDWARE GROUP NO\\. (?P<num>\\S+)",
  "row_start": "^\\d{1,3}$",
  "columns": [
    {"field": "qty", "x": 78}, {"field": "description", "x": 146},
    {"field": "catalog", "x": 288}, {"field": "finish", "x": 462}, {"field": "mfr", "x": 506}
  ]
}
```

The column at x=506 is the manufacturer column, so every `PE` or `NO` in it is a manufacturer for the whole book. That is how the brief's mfr vs finish caveat is decided, by position, never by the value.

![How a specbook becomes JSON](docs/diagrams/architecture.png)

## The assumption

One layout per book. A hardware schedule is written by one consultant with one tool, following DHI's sequence and format, so every set in a section looks the same. It held on all 20 sample books and on four public specs run cold ([RESULTS.md](docs/RESULTS.md)). The one book that changes layout, Star, does it at a section boundary, and it is the weakest score. Two formats the rules do not model yet, federal "A2111 by 623" rows and outline sets with no codes, are listed there with the one-rule fix for each.

## Where it stands

155 pages from 20 books labeled from page images, scored strictly with every field exact: 98.5% of 2,218 rows, 94.9% of 311 sets fully correct, 0 mfr/finish swaps. A held-out set of 25 pages scored after all tuning, with nothing changed in response: 98.6% of rows, 89.5% of sets. Across all 20 books, 1,174 of the 1,175 printed set numbers come out. Every spec in `specs/` was written by the API. How the labels were made, how the scorer works and where it loses are in the docs.

| Doc | What it covers |
| :--- | :--- |
| [PLAN.md](docs/PLAN.md) | The approach, what is built, what is open |
| [IMPLEMENTATION_BACKEND.md](docs/IMPLEMENTATION_BACKEND.md) | Extraction: goals, function trace, data structures |
| [IMPLEMENTATION_FRONTEND.md](docs/IMPLEMENTATION_FRONTEND.md) | Viewer: screens, API, build order |
| [CAVEATS.md](docs/CAVEATS.md) | The brief's tricky cases, with real examples |
| [BENCHMARK.md](docs/BENCHMARK.md) | Labels, scorer, checks |
| [RESULTS.md](docs/RESULTS.md) | Benchmark results, held-out set, unseen books |
| [APPROACHES.md](docs/APPROACHES.md) | Four approaches compared, what was ruled out |
| [APPROACH_RESULTS.md](docs/APPROACH_RESULTS.md) | How each approach scored |
| [DEMO.md](docs/DEMO.md) | The demo script |

## Running it

Needs [uv](https://docs.astral.sh/uv/). From the repo root:

```bash
uv sync
```

```bash
uv run hwsets extract "data/village-of-oswego/SPECIFICATIONS VOLUME 1.pdf" -o out/oswego.json
```

The 20 sample books have their specs checked in, so they run with no API key once the PDFs are under `data/` (see the benchmark section for where). A new book needs `ANTHROPIC_API_KEY` in the environment or in `.env` (see `.env.example`) for its one spec call, and a second call only if the audit flags something.

Output: one JSON per book. Each set has a number, description, status, page and box. Each row has `qty`, `description`, `catalog_number`, `mfr`, `finish`, `notes`, its own page and box, a confidence per field, and full names for codes the book explains in a printed legend.

## The viewer

```bash
uv run hwsets serve
```

Then http://localhost:8000.

- **Library.** Every PDF with its status and set count. Drop a new PDF on it and it is extracted on the spot.
- **Book view.** The page with a box per set beside the set's rows. Click a row to see it on the page. A CONF column scores each row, and a cell under 0.8 is tinted.
- **Fixing mistakes, no regex.** Double-click a cell to correct one value. Drag the column lines on the page to move a column for the whole book. Click a line and say what it is. Or type what is wrong and one model call edits the layout and reruns.
- **Checks, by URL.** `/#labels` shows each labeled page beside its label with nothing from the extractor, for a human to confirm the labels. `/#review` walks every disagreement between output and label.

## The benchmark

The PDFs are not in the repo. Copy the challenge's Drive folders into `data/`, one folder per project with the Drive folder names kept (`data/village-of-oswego/SPECIFICATIONS VOLUME 1.pdf`), since the checked-in specs are named after folder and file. Or put the folder ids in `scripts/drive_ids.txt`, one `folder_id:project-name` per line, and run:

```bash
scripts/download_data.sh
```

```bash
uv run python experiments/run_hwsets.py
```

```bash
cd experiments && uvx --from pdfplumber python3 bench_tags.py && uvx --from pdfplumber python3 bench.py out_hwsets
```

Included in the repo: all code, the specs in `specs/`, and the labels, tags and checks in `experiments/eval/`. The Drive share holds 43 PDFs across 21 projects. 20 contain hardware sets, 2 are second copies of a schedule already counted (Gerrard's full spec and Bridgeport's Rev 0), and the other 21 are the empty-book check.
