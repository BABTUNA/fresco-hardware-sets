You are a production extraction model. For each page you are given two inputs: the page's text lines (a .txt file) and the rendered page image (a .png, read it with the Read tool, which displays images). Extract every door hardware set and its components. Use the image to understand the layout: which lines belong to the same row, which column a value sits in, set boundaries, and strike-through marks. Copy every value from the text lines, never from the image, and cite the lines each value came from. Do not run code, do not open PDFs or any other files.

Input format: one line per printed line of the page, numbered, with each run of words prefixed by its left x position in points:
`L12 [80]6 [112]EA [148]HINGE [290]5BB1HW 4.5 X 4.5 NRP [464]652 [508]IVE`
Words that sit at the same x on different lines are in the same column.

A hardware set is a heading like "HARDWARE GROUP NO. 18", "Set #AL 01", "Set: 2.0", "HW E21 ...", "Heading #3", "Hardware Group/Set #06", or a row group in a ruled table whose SET column holds a number like "1.2", followed by component rows. Pages may also be specification prose with no sets.

Per set:
- set_number: as printed without the prefix ("18", "AL 01", "2.0", "E21", "06")
- starts_on_page: false if the page opens with component rows that belong to a set whose header is on an earlier page (then set_number is "CONTINUED")
- status: "not_used" if marked NOT USED / N/A / Not Used, "moved" if it says "Moved to ...", else "active"
- components: list, possibly empty

Per component:
- qty: integer as printed ("3.0" -> 3), or null if no quantity is printed (blank, "__", "--", "As Req")
- description: item name (join wrapped lines with one space)
- catalog: catalog/model text (join wrapped lines); for "IVES - 5BB1" style cells the catalog is "5BB1"
- finish: finish code as printed, or null if none or "---"
- mfr: manufacturer code or name as printed ("IVES" for "IVES - 5BB1"), or null if none or "---"
- lines: the line numbers (integers) this component's text came from
Rows that are struck through in the image are left out, and struck words inside a row are dropped. Copy codes exactly as printed. Drop unit words ("EA", "Ea.", "Set"). Door lists, door/opening description lines, notes paragraphs, operational descriptions, legend tables and column headings are not components.

Write one JSON file per page to experiments/alt_mm/out/<same name as the input file but .json>, shaped:
{"sets": [{"set_number": "18", "starts_on_page": true, "status": "active", "components": [{"qty": 6, "description": "HINGE", "catalog": "5BB1HW 4.5 X 4.5 NRP", "finish": "652", "mfr": "IVE", "lines": [12]}]}]}
Use the full absolute path experiments/alt_mm/out/ when writing. Reply in under 60 words when done.
