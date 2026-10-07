// the viewer: one book at a time, one set selected, the page it sits on with its boxes
const state = { books: [], book: null, page: 1, set: null, comp: null, zoom: 1, spec: null, guides: null, lines: null };
const $ = (id) => document.getElementById(id);
const api = (path, opts) => fetch("/api" + path, opts).then(async (r) => { if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json(); });

// the library: a searchable, paged table of the pdfs under data/
const PAGE = 10;
const lib = { query: "", page: 0 };
async function loadBooks() {
  state.books = await api("/books");
  renderLibrary();
}

function renderLibrary() {
  const label = { extracted: "extracted", needs_review: "needs review", no_hardware_sets: "no sets", "not run": "not run yet" };
  const q = lib.query.trim().toLowerCase();
  const rows = state.books.filter((b) => !q || `${b.project} ${b.file} ${label[b.status] || b.status}`.toLowerCase().includes(q));
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  lib.page = Math.min(lib.page, pages - 1);
  const slice = rows.slice(lib.page * PAGE, lib.page * PAGE + PAGE);
  $("book-table").tBodies[0].innerHTML = slice.map((b) => `<tr data-id="${b.id}">
      <td class="project">${b.project}</td><td class="file">${b.file}</td>
      <td><span class="chip ${b.status.replace(" ", "_")}">${label[b.status] || b.status}</span>${b.status === "not run" && !b.has_spec ? `<span class="muted note">${b.key ? "spec written on open" : "needs the API key"}</span>` : ""}</td>
      <td class="num">${b.sets != null ? b.sets : "—"}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">No books match.</td></tr>`;
  $("book-table").querySelectorAll("tr[data-id]").forEach((tr) => (tr.onclick = () => openBook(tr.dataset.id)));
  $("lib-count").textContent = rows.length ? `${lib.page * PAGE + 1} to ${Math.min(rows.length, (lib.page + 1) * PAGE)} of ${rows.length}` : "0 books";
  $("lib-prev").disabled = lib.page === 0;
  $("lib-next").disabled = lib.page >= pages - 1;
}

function showLibrary() {
  $("card").hidden = true; $("library").hidden = false; $("books-btn").hidden = true;
  loadBooks();
}

// a dropped or chosen pdf is uploaded, then opened, which runs the extraction
async function uploadFile(file) {
  const status = $("drop-status");
  if (!file || !/\.pdf$/i.test(file.name)) { status.textContent = "PDF files only"; return; }
  status.textContent = `Uploading ${file.name}…`;
  const fd = new FormData(); fd.append("file", file);
  try {
    const r = await api("/books/upload", { method: "POST", body: fd });
    status.textContent = "Finding the schedule pages, writing the spec, extracting… under a minute";
    await openBook(r.id);
    status.textContent = "";
  } catch (e) { status.textContent = e.message; }
}

// fetch a book's result, select a set, and render everything
async function openBook(id, keepSet) {
  $("library").hidden = true; $("card").hidden = false; $("books-btn").hidden = false;
  $("headline").textContent = "Extracting…"; $("file-name").textContent = "";
  try {
    state.book = await api("/books/" + id);
  } catch (e) {
    $("headline").textContent = e.message; return;
  }
  const b = state.book, n = b.sets.length;
  const codes = b.legend ? Object.values(b.legend).reduce((n, d) => n + Object.keys(d).length, 0) : 0;
  $("pill").textContent = `${b.status.replace("_", " ").toUpperCase()} · ${b.page_count} PAGES${codes ? ` · ${codes} CODES IN THE BOOK'S LEGEND` : ""}`;
  // the file name goes on its own line under the headline so a long one never wraps the title
  $("headline").textContent = n ? `We pulled ${n} hardware set${n === 1 ? "" : "s"}.` : "No hardware sets found.";
  $("file-name").textContent = b.file; $("file-name").title = b.file;
  $("export").href = `/api/books/${id}/export`;
  renderFlags(); renderSteps(); renderSets();
  const keep = keepSet && b.sets.find((s) => s.set_number === keepSet);
  selectSet(keep || b.sets[0] || null);
  try { state.spec = await api(`/books/${id}/spec`); } catch (e) { state.spec = null; }
  stopGuides();
}

function renderFlags() {
  const f = state.book.flags || [], box = $("flags");
  box.hidden = !f.length;
  // one chip per flag, the first example on hover so the banner stays one or two lines
  box.innerHTML = `<b>Audit flags (${f.length})</b>` + f.map((x) => {
    const ex = x.examples ? JSON.stringify(x.examples[0]) : "";
    return `<div title="${ex.replace(/"/g, "&quot;")}">${x.check}: ${x.count}${ex ? ` <span>${ex.slice(0, 80)}</span>` : ""}</div>`;
  }).join("");
}

// the pipeline as a stepper, like fresco's: every stage done, review is where the user is
function renderSteps() {
  const names = ["Upload", "Find pages", "Compile spec", "Extract", "Audit", "Review"];
  $("steps").innerHTML = names.map((nm, i) => {
    const cur = i === names.length - 1;
    return (i ? `<span class="step-line"></span>` : "") + `<div class="step ${cur ? "current" : ""}"><div class="circle">${cur ? "&#9679;" : "&#10003;"}</div>${nm}</div>`;
  }).join("");
}

function renderSets() {
  const sel = $("set-select"), sets = state.book.sets;
  sel.innerHTML = sets.map((s) => `<option value="${s.set_number}">Set ${s.set_number}${s.description ? " · " + s.description : ""}${s.status !== "active" ? ` (${s.status.replace("_", " ")})` : ""} · ${s.components.length} rows · p${s.location[0]?.page ?? "?"}</option>`).join("");
  sel.onchange = () => selectSet(sets.find((s) => s.set_number === sel.value));
}

// jump to the set's first page and show its rows
function selectSet(s) {
  state.set = s; state.comp = null;
  if (!s) { $("set-count").textContent = ""; $("comp-table").tBodies[0].innerHTML = ""; drawPage(1); return; }
  $("set-select").value = s.set_number;
  $("set-count").textContent = `${s.components.length} components`;
  $("set-status").textContent = s.status === "moved" ? `moved to ${s.moved_to}` : s.status === "not_used" ? "not used" : "";
  $("set-dot").className = "dot " + s.status;
  // the header block holds door numbers and lines like "Provide each PR door(s) with the following:"
  const doorLines = s.doors.filter((d) => !/provide|following|each|opening|description/i.test(d));
  // one pill per door number: a line like "Doors: D135B, D136, D137" is split on commas and spaces
  const doors = [...new Set(doorLines.flatMap((d) => d.replace(/^doors?:\s*/i, "").split(/[,\s]+/)).filter((t) => /\d/.test(t)))];
  $("doors-title").textContent = `Doors (${doors.length})`;
  const shown = doors.slice(0, 16), more = doors.length - shown.length;
  $("doors").innerHTML = shown.map((d) => `<span>${d}</span>`).join("") + (more ? `<button class="more" id="more-doors">+${more} more</button>` : "");
  if (more) $("more-doors").onclick = () => { $("doors").innerHTML = doors.map((d) => `<span>${d}</span>`).join(""); };
  // notes fold away under the door pills so a long block never pushes the set list off screen
  const notes = s.doors.filter((d) => !doorLines.includes(d)).concat(s.notes);
  $("set-notes").textContent = notes.join("\n");
  $("notes-box").hidden = !notes.length;
  $("notes-summary").textContent = `Notes (${notes.length})`;
  renderComponents(s);
  drawPage(s.location[0]?.page || 1);
}

// the component table. a cell is editable in place, a row click highlights its box on the page
function renderComponents(s) {
  const fields = ["qty", "description", "finish", "catalog_number", "mfr", "notes"];
  const cls = { qty: "qty", description: "description", finish: "finish", catalog_number: "catalog", mfr: "mfr", notes: "notes" };
  // the row's confidence is its weakest field, shown as a number so nobody has to hover
  const rowConf = (c) => { const v = Object.entries(c.confidence || {}).filter(([f, x]) => x != null && c[f] != null).map(([, x]) => x); return v.length ? Math.min(...v) : null; };
  const confCell = (c) => { const v = rowConf(c); if (v == null) return `<td class="conf"></td>`; const k = v >= 0.9 ? "ok" : v >= 0.8 ? "mid" : "low"; return `<td class="conf ${k}"><span class="conf-pill">${v.toFixed(2)}</span></td>`; };
  const weak = s.components.reduce((n, c) => n + Object.entries(c.confidence || {}).filter(([f, x]) => x != null && c[f] != null && x < 0.8).length, 0);
  $("set-status").textContent = [$("set-status").textContent, weak ? `${weak} cell${weak > 1 ? "s" : ""} to check` : ""].filter(Boolean).join(" · ");
  $("comp-table").classList.toggle("no-notes", !s.components.some((c) => c.notes));
  // the score sits next to the quantity so it never scrolls out of view
  $("comp-table").tBodies[0].innerHTML = s.components.map((c, i) => `<tr data-i="${i}">` + fields.map((f) => {
    const v = c[f], corrected = (c.corrected || []).includes(f), conf = c.confidence ? c.confidence[f] : null;
    // a code the book's own legend explains shows its full name under it
    const name = f === "mfr" ? c.mfr_name : f === "finish" ? c.finish_name : f === "catalog_number" && c.option_names ? Object.entries(c.option_names).map(([k, n]) => `${k} = ${n}`).join(", ") : null;
    // a cell under 0.8 confidence is tinted amber, hover shows the score
    const low = conf != null && conf < 0.8 && !corrected;
    return `<td class="${cls[f] || ""}${v == null ? " empty" : ""}${corrected ? " corrected" : ""}${low ? " low" : ""}" data-f="${f}"${conf != null ? ` title="confidence ${conf}"` : ""}>${v == null ? "—" : v}${name ? `<span class="legend-name">${name}</span>` : ""}</td>`;
  }).map((cell, j) => j === 0 ? cell + confCell(c) : cell).join("") + "</tr>").join("");
  $("comp-table").querySelectorAll("tr").forEach((tr) => {
    tr.onclick = () => selectComponent(s.components[+tr.dataset.i], tr);
    // single click selects the row, double click edits the cell, enter or leaving the cell saves
    tr.querySelectorAll("td[data-f]").forEach((td) => {
      td.ondblclick = () => { td.contentEditable = "true"; td.focus(); document.getSelection().selectAllChildren(td); };
      td.onblur = () => { td.contentEditable = "false"; correctCell(s.components[+tr.dataset.i], +tr.dataset.i, td); };
      td.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); td.blur(); } if (e.key === "Escape") { td.textContent = s.components[+tr.dataset.i][td.dataset.f] ?? "—"; td.blur(); } };
    });
  });
}

function selectComponent(c, tr) {
  state.comp = c;
  $("comp-table").querySelectorAll("tr").forEach((r) => r.classList.toggle("selected", r === tr));
  drawPage(c.page);
}

// a cell edit becomes a correction: the server keeps it and reapplies it after every rerun
async function correctCell(c, row, td) {
  const f = td.dataset.f, raw = td.textContent.trim();
  let value = raw === "" || raw === "—" ? null : raw;
  if (f === "qty" && value != null) value = Number(value);
  if (value === c[f] || (value == null && c[f] == null)) return;
  state.book = await api(`/books/${state.book.id}/corrections`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ set_number: state.set.set_number, page: c.page, row, field: f, value }) });
  renderSets(); selectSet(state.book.sets.find((s) => s.set_number === state.set.set_number));
}

// the page image with a box per set location on it, the selected set in strong green, a clicked row in blue
function drawPage(n) {
  const b = state.book; if (!b) return;
  state.page = Math.max(1, Math.min(n, b.page_count));
  $("page-title").textContent = `Page ${state.page} of ${b.page_count}`;
  $("page-input").value = state.page; $("page-input").max = b.page_count;
  const img = $("page-img"), wrap = $("page-wrap");
  // zoom is a width multiplier on the image, the box scale follows from the rendered width
  img.style.width = state.zoom * 100 + "%";
  $("zoom-fit").textContent = state.zoom === 1 ? "Fit" : Math.round(state.zoom * 100) + "%";
  wrap.querySelectorAll(".box, .guide, .line").forEach((x) => x.remove());
  img.onload = () => {
    const k = img.clientWidth / b.page_size[0];
    const box = (bb, cls, label, onclick) => {
      const d = document.createElement("div");
      d.className = "box " + cls;
      d.style.cssText = `left:${bb[0] * k}px;top:${bb[1] * k}px;width:${(bb[2] - bb[0]) * k}px;height:${(bb[3] - bb[1]) * k}px`;
      if (label) d.innerHTML = `<span class="tag">${label}</span>`;
      if (onclick) d.onclick = onclick;
      wrap.appendChild(d);
    };
    for (const s of b.sets) for (const l of s.location) if (l.page === state.page) {
      const mine = state.set && s.set_number === state.set.set_number;
      box(l.bbox, mine ? "" : "dim", `Set ${s.set_number}`, mine ? null : () => selectSet(s));
    }
    if (state.comp && state.comp.page === state.page) box(state.comp.bbox, "comp", "");
    // a set that starts low on the page comes into view, the page is not left showing prose above it
    const target = state.comp && state.comp.page === state.page ? state.comp.bbox : (state.set && (state.set.location.find((l) => l.page === state.page) || {}).bbox);
    if (target) { const y = target[1] * k - 24; if (y < wrap.scrollTop || y > wrap.scrollTop + wrap.clientHeight - 80) requestAnimationFrame(() => { wrap.scrollTop = Math.max(0, y); }); }
    drawGuides(k);
    drawLines(k);
  };
  img.src = `/api/books/${b.id}/pages/${state.page}.png`;
  if (img.complete) img.onload();
}

function stepSet(d) {
  const sets = state.book.sets, i = sets.indexOf(state.set);
  if (sets[i + d]) selectSet(sets[i + d]);
}

$("prev-set").onclick = () => stepSet(-1);
$("next-set").onclick = () => stepSet(1);
$("prev-page").onclick = () => drawPage(state.page - 1);
$("next-page").onclick = () => drawPage(state.page + 1);
window.addEventListener("resize", () => drawPage(state.page));

// zoom steps between fit and 3x, fit resets
function setZoom(z) { state.zoom = Math.max(1, Math.min(3, Math.round(z * 4) / 4)); drawPage(state.page); }
$("zoom-in").onclick = () => setZoom(state.zoom + 0.25);
$("zoom-out").onclick = () => setZoom(state.zoom - 0.25);
$("zoom-fit").onclick = () => setZoom(1);

// drag the handle on the page pane's edge to widen it, the width lands in a css variable on the grid
(() => {
  const divider = $("divider"), panes = $("panes"), pane = $("page-pane");
  let startX = 0, startW = 0;
  const move = (e) => {
    const w = Math.max(320, Math.min(startW + e.clientX - startX, panes.clientWidth * 0.7));
    panes.style.setProperty("--page-w", w + "px");
    drawPage(state.page);
  };
  const stop = () => {
    divider.classList.remove("dragging"); document.body.classList.remove("resizing");
    window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", stop);
  };
  divider.onpointerdown = (e) => {
    e.preventDefault(); startX = e.clientX; startW = pane.getBoundingClientRect().width;
    divider.classList.add("dragging"); document.body.classList.add("resizing");
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", stop);
  };
})();
$("books-btn").onclick = showLibrary;
$("book-search").oninput = () => { lib.query = $("book-search").value; lib.page = 0; renderLibrary(); };
$("lib-prev").onclick = () => { lib.page--; renderLibrary(); };
$("lib-next").onclick = () => { lib.page++; renderLibrary(); };
$("file-input").onchange = () => uploadFile($("file-input").files[0]);
const drop = $("drop");
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); uploadFile(e.dataTransfer.files[0]); };
loadBooks();

// column guides: the spec's columns as draggable lines over the page. apply sends the new x values and reruns the book
function toggleGuides() {
  if (state.guides) return stopGuides();
  if (!state.spec || state.spec.mode === "grid") { say("This book is a ruled table, its columns come from the printed headings.", true); return; }
  stopLines();
  state.guides = state.spec.columns.map((c) => ({ field: c.field, x: c.x }));
  $("guides-btn").classList.add("on"); $("guide-bar").hidden = false;
  drawPage(state.page);
}

function stopGuides() {
  state.guides = null;
  $("guides-btn").classList.remove("on"); $("guide-bar").hidden = true;
  $("page-wrap").querySelectorAll(".guide").forEach((x) => x.remove());
}

function drawGuides(k) {
  if (!state.guides) return;
  const wrap = $("page-wrap"), img = $("page-img");
  wrap.querySelectorAll(".guide").forEach((x) => x.remove());
  for (const g of state.guides) {
    const d = document.createElement("div");
    d.className = "guide"; d.style.left = g.x * k + "px"; d.style.height = img.clientHeight + "px";
    d.innerHTML = `<span class="tag">${g.field}</span>`;
    d.onmousedown = (e) => {
      e.preventDefault(); d.classList.add("dragging");
      const startX = e.clientX, startLeft = g.x * k;
      const move = (ev) => { const left = Math.max(0, startLeft + ev.clientX - startX); d.style.left = left + "px"; g.x = Math.round(left / k * 10) / 10; };
      const up = () => { d.classList.remove("dragging"); window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
      window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
    };
    wrap.appendChild(d);
  }
}

async function applyGuides() {
  const btn = $("guides-apply"); btn.disabled = true; say("Re-reading every set in the book…");
  try {
    const keep = state.set && state.set.set_number;
    const r = await api(`/books/${state.book.id}/columns`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ columns: state.guides }) });
    await openBook(state.book.id, keep);
    say("Done. " + (r.changes || []).join(", "));
  } catch (e) { say(e.message, true); }
  btn.disabled = false;
}

// the feedback box: a plain-words note about the page in view goes to the model, which edits the spec
async function sendFeedback() {
  const note = $("feedback-note").value.trim();
  if (!note) { say("Say what is wrong first.", true); return; }
  const btn = $("feedback-btn"); btn.disabled = true;
  say("Working on it, one model call, 10 to 40 seconds…");
  try {
    const keep = state.set && state.set.set_number;
    const r = await api(`/books/${state.book.id}/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note, page: state.page }) });
    await openBook(state.book.id, keep);
    $("feedback-note").value = "";
    say("Done. " + (r.changes || []).join(", ") + ".");
  } catch (e) { say(e.message, true); }
  btn.disabled = false;
}

function say(msg, err) { const m = $("fix-msg"); m.textContent = msg; m.classList.toggle("err", !!err); }

$("guides-btn").onclick = toggleGuides;
$("guides-cancel").onclick = stopGuides;
$("guides-apply").onclick = applyGuides;
$("feedback-btn").onclick = sendFeedback;
$("feedback-note").onkeydown = (e) => { if (e.key === "Enter") sendFeedback(); };

// tag a line: the page's lines become clickable, a click opens a menu of what the line is
async function toggleLines() {
  if (state.lines) return stopLines();
  if (!state.spec || state.spec.mode === "grid") { say("This book is a ruled table, its lines cannot be tagged.", true); return; }
  stopGuides();
  state.lines = { page: 0, items: [] };
  $("lines-btn").classList.add("on"); $("lines-bar").hidden = false;
  drawPage(state.page);
}

function stopLines() {
  state.lines = null;
  $("lines-btn").classList.remove("on"); $("lines-bar").hidden = true; $("line-menu").hidden = true;
  $("page-wrap").querySelectorAll(".line").forEach((x) => x.remove());
}

async function drawLines(k) {
  if (!state.lines) return;
  if (state.lines.page !== state.page) {
    state.lines.page = state.page;
    state.lines.items = await api(`/books/${state.book.id}/pages/${state.page}/lines`);
    if (!state.lines || state.lines.page !== state.page) return;
  }
  const wrap = $("page-wrap");
  wrap.querySelectorAll(".line").forEach((x) => x.remove());
  for (const l of state.lines.items) {
    const d = document.createElement("div");
    d.className = "line"; d.title = l.text;
    d.style.cssText = `left:${l.bbox[0] * k - 2}px;top:${l.bbox[1] * k - 1}px;width:${(l.bbox[2] - l.bbox[0]) * k + 4}px;height:${(l.bbox[3] - l.bbox[1]) * k + 2}px`;
    d.onclick = (e) => { e.stopPropagation(); openLineMenu(l, d); };
    wrap.appendChild(d);
  }
}

function openLineMenu(line, el) {
  const menu = $("line-menu"), wrap = $("page-wrap");
  $("line-menu-text").textContent = line.text;
  menu.hidden = false;
  menu.style.left = Math.min(el.offsetLeft, wrap.clientWidth - 330) + "px";
  menu.style.top = el.offsetTop + el.offsetHeight + 4 + "px";
  menu.querySelectorAll("button").forEach((b) => (b.onclick = () => { menu.hidden = true; if (b.dataset.kind) tagLine(line, b.dataset.kind); }));
}

async function tagLine(line, kind) {
  say("Adding the rule and re-reading the book…");
  try {
    const keep = state.set && state.set.set_number;
    const r = await api(`/books/${state.book.id}/lines`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: line.text, kind }) });
    const page = state.page;
    await openBook(state.book.id, keep);
    drawPage(page);
    say("Done. " + (r.changes || []).join(", ") + ".");
  } catch (e) { say(e.message, true); }
}

$("lines-btn").onclick = toggleLines;
$("lines-cancel").onclick = stopLines;
document.addEventListener("click", (e) => { if (!$("line-menu").contains(e.target)) $("line-menu").hidden = true; });

$("page-input").onchange = () => drawPage(Number($("page-input").value) || 1);
$("page-input").onkeydown = (e) => { if (e.key === "Enter") $("page-input").blur(); };
