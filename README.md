# fresco-hardware-sets

Extracts door hardware sets from Division 08 spec PDFs for the Fresco take-home. This is the research and experiment stage. The clean build has not started yet.

## The idea

Each specbook uses one layout for all of its sets. Instead of sending every page to a model, a model reads 2 schedule pages once and writes a short layout spec for the book. Plain code then reads every page with that spec.

Oswego's spec, shortened:

```json
{
  "set_header": "^HARDWARE GROUP NO\\. (?P<num>\\S+)",
  "row_start": "^\\d{1,3}$",
  "columns": [
    {"field": "qty", "x": 78}, {"field": "unit", "x": 110}, {"field": "description", "x": 146},
    {"field": "catalog", "x": 288}, {"field": "finish", "x": 462}, {"field": "mfr", "x": 506}
  ]
}
```

The column at x=506 is the manufacturer column, so every `PE` or `ZER` in it is a manufacturer for the whole book. Every value comes from real words on the page, so each set gets an exact page and bounding box.

## Where it stands

On 155 labeled pages from 20 books (labeled from page images, see [BENCHMARK.md](docs/BENCHMARK.md)), 98.4% of the 2,218 labeled rows come out exactly right with every field correct, and 94.5% of the 311 sets are fully correct. On a separate held-out set of 25 pages scored once after all tuning, it is 97.2% of rows and 89.5% of sets. Across all 20 books, 1,172 of the 1,175 set numbers printed in the PDFs are in the output. In the experiments a Claude subagent stood in for the API call that writes each spec.

| Doc | What it covers |
| :--- | :--- |
| [PLAN.md](docs/PLAN.md) | The approach and build order |
| [IMPLEMENTATION_BACKEND.md](docs/IMPLEMENTATION_BACKEND.md) | Extraction: goals, function trace, data structures |
| [IMPLEMENTATION_FRONTEND.md](docs/IMPLEMENTATION_FRONTEND.md) | Viewer: screens, API, state, build order |
| [CAVEATS.md](docs/CAVEATS.md) | The tricky cases from the brief, with real examples |
| [BENCHMARK.md](docs/BENCHMARK.md) | How the benchmark works |
| [RESULTS.md](docs/RESULTS.md) | Benchmark results |
| [APPROACHES.md](docs/APPROACHES.md) | The four approaches compared, and what was ruled out |
| [APPROACH_RESULTS.md](docs/APPROACH_RESULTS.md) | How each approach scored on the benchmark |

## Running the benchmark

The specbook PDFs are not in this repo. Put the challenge's Drive folder ids in `scripts/drive_ids.txt`, one `folder_id:project-name` per line, then download:

```bash
scripts/download_data.sh
```

Then from `experiments/`:

```bash
uvx --from pdfplumber python3 e2e.py .r1
```

```bash
uvx --from pdfplumber python3 bench_tags.py
```

```bash
uvx --from pdfplumber python3 bench.py
```

```bash
uvx --from pdfplumber python3 bench_checks.py
```

## What is and is not in the repo

Included: all code, the compiled specs in `experiments/specs_e2e/`, and the benchmark labels, tags and checks in `experiments/eval/`.

Left out: the PDFs, rendered page images, page text dumps, and full extraction output, since they copy the challenge material wholesale.
