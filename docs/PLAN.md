# Hardware sets: implementation plan

## The idea

Each specbook uses one layout for all its sets. So instead of sending every page to a model, the model looks at 2 schedule pages once and writes a short layout spec for the book. Plain code then reads every page with that spec.

Oswego's compiled spec (shortened):

```json
{
  "set_header": "^HARDWARE GROUP NO\\. (?P<num>\\S+)",
  "row_start": "^\\d{1,3}$",
  "columns": [
    {"field": "qty", "x": 78}, {"field": "unit", "x": 110}, {"field": "description", "x": 146},
    {"field": "catalog", "x": 288}, {"field": "finish", "x": 462}, {"field": "mfr", "x": 506}
  ],
  "skip": ["^Village of Oswego", "^087100 - \\d+$"]
}
```

The spec says the column at x=506 is the manufacturer column. So every `ZER`, `PE` or `B/O` in that column is a manufacturer, for the whole book. That is how mfr vs finish gets decided.

## Pipeline

```
PDF -> 1. find schedule pages -> 2. compile spec (1 LLM call) -> 3. interpret every page
    -> 4. audit -> (flags? 1 repair call, back to 3) -> 5. JSON with page + bbox per set
```

| Step | What it does | Proven in |
| :--- | :--- | :--- |
| **1. Find** | Scores every page by how many lines look like component rows (qty, words, short codes at the end) plus hardware words. No header wording needed. | `experiments/finder.py` |
| **2. Compile** | Sends the 2 densest pages, as text tagged with x positions, to Claude. Gets back the spec JSON. | subagent stand-in |
| **3. Interpret** | Assigns words to fields by x. Merges wrapped lines, handles centered cells, missing qty, sets across pages, NOT USED and "moved to" sets, grid tables. Re-snaps right-hand columns per page. | `experiments/spec_parse.py` |
| **4. Audit** | Checks the result against the book: header-like lines that did not match, pages with rows but no components, long text in code columns, mfr column that looks like finishes. | `experiments/e2e.py` |
| **5. Output** | Sets with 1-based page numbers, bbox per page and per component, statuses. | |

**Results so far.** On 155 labeled pages from 20 books, scored strictly: 94.9% of sets fully correct, 98.5% of rows exact, 98.6% precision, 0 mfr/finish swaps in 2,218 rows. Across whole books, 1,174 of 1,175 printed set numbers are found. See [RESULTS.md](RESULTS.md).

## Output

```json
{
  "file": "SPECIFICATIONS VOLUME 1.pdf",
  "status": "extracted",
  "sets": [{
    "set_number": "18",
    "description": null,
    "doors": ["E120A", "E121B"],
    "status": "active",
    "location": [{"page": 427, "bbox": [72.0, 73.5, 530.2, 630.5]}],
    "components": [
      {"qty": 6, "description": "HINGE", "catalog_number": "5BB1HW 4.5 X 4.5 - NRP AT OUTSWINGING DRS",
       "mfr": "IVE", "finish": "652", "notes": null,
       "page": 427, "bbox": [80.1, 98.2, 528.0, 121.7], "confidence": 0.97}
    ],
    "notes": ["OPERATIONAL DESCRIPTION: ENTRANCE BY CREDENTIAL READER ..."]
  }]
}
```

- bbox is in PDF points, origin top left, with page width and height in the file header so the viewer can scale it.
- Book `status` is `extracted`, `no_hardware_sets` (finder found nothing) or `needs_review` (audit flags left after repair).
- Set `status` is `active`, `not_used` or `moved` (with `moved_to`).

## Repo layout

```
fresco/
  hwsets/
    lines.py      words to lines, strike marks
    finder.py     step 1, and the header widening after the spec exists
    spec.py       spec schema and interpreter (columns and grid modes)
    compile.py    step 2 and the repair call (Anthropic API)
    audit.py      step 4
    legend.py     code lists printed in the book, to full names
    extract.py    runs the pipeline, confidence scores, writes the output JSON
    cli.py        hwsets extract book.pdf -o out.json, hwsets serve
    prompts/      spec compile and repair prompts
  specs/          compiled spec per sample book, checked in
  app/            the viewer: server.py and one static page
  experiments/    the research: finder and interpreter prototypes, the benchmark (eval/, bench.py), the alternatives
  scripts/download_data.sh
  README.md
```

**Checked-in specs.** A reviewer can run every sample book without an API key and get the same output I got. The key is only needed for a new book.

**Size.** `hwsets/` is about 900 lines with comments, the viewer about 500.

## Build order

Done, in this order:

1. Port the core from `experiments/` into `hwsets/` with the output schema above. Reproduced the benchmark exactly.
2. The known residuals (struck rows, door-number lines, note lines glued to rows, hyphen joins, "As Req" rows) were fixed in the experiments before the port.
3. Compile and repair through the API. All 20 specs recompiled fresh: 98.5% rows, 94.9% sets, 1,174 of 1,175 printed set numbers.
4. Eval: the strict scorer on 155 labeled pages plus 25 held out, in `experiments/`.
5. CLI and README.
6. Viewer: library with a drop zone, page image with a box per set, components table, corrections by double-click.
7. Confidence scores per field, shown as a CONF column.
8. Code resolution from the legends four books print.
9. Feedback without regex: draggable column guides, tag a line, and a plain-words box that goes to the repair call.

Still open:

10. Demo video. Library, drop a PDF, Oswego, Star page 107 with tag a line, the numbers.
11. Deploy, or leave the local run steps.

## Decided

- Approach: compile one spec per book, interpret deterministically.
- LLM: Anthropic API, `claude-sonnet-5-5`, key in `.env`. One call per book, a second only when the audit flags.
- UI: a viewer where a reviewer never sees the spec. Column guides, tagged lines and a feedback box edit it for them.
- Text layer only. Every sample book has one. Scanned PDFs return `needs_review`.

## Open

- Deploy target, if any.

## Risks

- **The eval is model-labeled.** 155 pages plus 25 held out, labeled by Claude from page images, two labelers agreeing 99% of the time. Mismatches were checked by hand and a few turned out to be labeler errors. A hand check of a sample of sets by a person is still worth doing before quoting the number as fact.
- **A spec can be wrong in a way the audit does not see.** HFH looked fine on recall while 10 sets were merged. More audit checks are cheap, so add one for each failure found.
- **Books that switch layouts mid-schedule.** Star does this a little and per-page calibration covered it. A book with two truly different layouts would need one spec per page run.
