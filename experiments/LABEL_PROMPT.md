You are creating ground-truth labels for a benchmark. Transcribe door hardware sets from rendered PDF page IMAGES only. Do not run code. Do not open PDFs or any files other than the images you are given. Read each PNG with the Read tool (it displays images). Look carefully and transcribe codes EXACTLY as printed, even if they look like typos; never substitute a "real" part number.

For each image, list every hardware set that appears on that page, in order. A set may continue from the previous page: use its set number if a "continued" note shows it, otherwise "CONTINUED". Set headers look like "Hardware Group No. 18", "Set #AL 01", "Set: 2.0", "HW E21 ...", "Heading #3", "Hardware Group/Set #06", or a row group in a ruled table whose SET column holds a number like "1.2".

Per set record:
- set_number: as printed without the "Set #"/"HW"/"Hardware Group No." prefix (e.g. "18", "AL 01", "2.0", "E21", "06")
- starts_on_page: false if the set's header is on an earlier page
- continues_on_next_page: true if the set's last component on this page is not the end of the set (no new header or end of schedule follows it on this page and the page ends mid-set)
- status: "not_used" if marked NOT USED / N/A / Not Used, "moved" if it says "Moved to ...", else "active"
- components: list, possibly empty

Per component visible ON THIS PAGE:
- qty: number as printed (integer; "3.0" -> 3), or null if no quantity is printed (blank, "__", "--", "As Req")
- description: item name text (join wrapped lines with a single space)
- catalog: catalog/model text (join wrapped lines); if manufacturer and product share a cell like "IVES - 5BB1", catalog is "5BB1"
- finish: finish code as printed, or null if none or "---"
- mfr: manufacturer code/name as printed (for "IVES - 5BB1" it is "IVES"), or null if none or "---"

Not components: unit words like "EA" (drop them), door lists and door/opening description lines (e.g. "1 Single Door #104 ... 105° RH", "Opening Description: ..."), set-level prose (operational descriptions, "Note:" paragraphs), legend tables (manufacturer/finish/option lists), column heading rows. Rows that are struck through (a line drawn through them) are excluded; struck words inside a row are dropped. If a page has no hardware sets, record an empty list.

Write one JSON file per image to experiments/eval/gt/<image name without .png>.json:
{"page_image": "lyons_p284.png", "sets": [{"set_number": "05", "starts_on_page": true, "continues_on_next_page": false, "status": "not_used", "components": []}]}
Reply in under 100 words with any pages or judgment calls that were hard.
