You wrote the layout spec below for a door hardware schedule, and an audit of the extraction it produced found the problems listed under "Audit flags". Revise the spec so the flagged lines are handled, keeping everything that already works. Reply with the full revised JSON only.

What the flags mean:
- `header_near_miss`: these lines look like set headers but `set_header` did not match them. Widen the regex (plural forms, a space in the number, an unanchored start, a different separator).
- `rows_without_components`: these pages have component rows and nothing was extracted. Usually a column x is wrong, `row_start` is too strict, or a `skip` or `set_meta` pattern matches real rows.
- `long_text_in_code_columns`: finish or mfr cells hold sentences, so a column x is too far left.
- `mfr_looks_like_finish`: the mfr column holds finish codes (626, US26D), so the finish and mfr columns are swapped or shifted.
- `low_coverage`: far fewer components than row-shaped lines. Same causes as rows_without_components.
- `suspicious_qty`: a door-number line was read as a row. Add it to `set_meta` or `skip`.
- `many_empty_sets`: headers matched but their rows did not. Check `row_start` and the column x values.

The spec format is the same as before: columns mode with set_header, row_start, columns, valign, skip, set_meta, note_line, end; or grid mode with set_column, set_number, columns, mfr_split.
