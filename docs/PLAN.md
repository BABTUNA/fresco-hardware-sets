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
    lines.py      words to lines, drops rotated watermark text
    finder.py     step 1
    spec.py       spec schema and interpreter (columns and grid modes)
    compile.py    step 2 and the repair call (Anthropic API)
    audit.py      step 4
    legend.py     code lookup tables printed in the book (bonus)
    extract.py    runs the pipeline, writes the output JSON
    cli.py        hwsets extract book.pdf -o out.json, hwsets serve
    prompts/      spec compile and repair prompts
  specs/          compiled spec per sample book, checked in
  eval/
    gt/           labeled pages
    score.py
  app/            viewer
  scripts/download_data.sh
  README.md
```

**Checked-in specs.** A reviewer can run every sample book without an API key and get the same output I got. The key is only needed for a new book.

**Size.** Keep `hwsets/` under about 800 lines. It is about 560 now in `experiments/`.

## Build order

1. **Port the core.** Move `lines`, `finder`, `spec_parse`, and the audit from `experiments/` into `hwsets/`, cleaned up, with the output schema above.
2. **Fix the known residuals** from the experiments:

   | Problem | Seen in | Fix |
   | :--- | :--- | :--- |
   | Struck-through rows and words are kept | HFH, SJC, Valor | Thin lines through a word's mid-height mark it struck. Drop struck words, mark struck rows `removed`. |
   | Door-number line read as a row with qty 115 | Lyons | Audit flags qty over 99 with no catalog |
   | Set-note line glued onto the last row's description | Gerrard | Treat a line under the last row as a note when it ends with ":" or the row already has all its code columns |
   | Hyphen join fires inside a line | Bridgeport | Only join across line breaks |
   | "As Req" qty row not anchored | SJC | Let `row_start` match words, qty stays null |

3. **Compile and repair with Claude.** The prompt is `experiments/SPEC_PROMPT.md`. Validate the reply against the spec JSON schema. Repair gets the spec, the audit flags, and the same 2 pages. One repair round max, then `needs_review`.
4. **Eval.** Move the 39 labeled pages into `eval/gt/`, port the scorer, and print one table per book plus the total. This is the headline number for the README.
5. **CLI and README.** Setup with `uv`, the download script, one command per sample book.

**Cut line: the submission is complete here.**

6. **Viewer.** One page: pick a book, see the PDF page with a box per set, click a set to see its components next to it. The compiled spec sits in an editor beside it. Editing it reruns the interpreter and every set in the book updates.
7. **Confidence scores.** Per field, from evidence the pipeline already has: did the column snap to an aligned edge on this page, does the value have the shape of its column (finish code vs mfr code), did the set pass the audit.
8. **Code resolution from legends.** Gerrard and Forest Park print Manufacturer, Finish and Option lists before the sets (`HA = Hager`, `C = Charcoal`). Parse those code/name blocks and add `mfr_name` and `finish_name`.

**Cut line: bonus points done.**

9. **Deploy.** On hold until the rest is done.
10. **Demo video.** Oswego (wrapped rows), Roselle (grid table, 13 sets per page), JC Ryan (centered cells), then HFH to show the audit catching 10 merged sets and the repair fixing them.

## Decided

- Approach: compile one spec per book, interpret deterministically.
- LLM: Anthropic API, key in `.env`.
- UI: viewer plus spec editing.
- Text layer only. Every sample book has one. Scanned PDFs return `needs_review`.

## Open

- Deploy target.
- Which Claude model compiles specs. Try the cheaper one first and keep it if the eval holds.

## Risks

- **The eval is small and model-labeled.** 39 pages. Every mismatch was checked by hand and 3 turned out to be labeler errors. I should label a few more pages myself before quoting the number.
- **A spec can be wrong in a way the audit does not see.** HFH looked fine on recall while 10 sets were merged. More audit checks are cheap, so add one for each failure found.
- **Books that switch layouts mid-schedule.** Star does this a little and per-page calibration covered it. A book with two truly different layouts would need one spec per page run.
