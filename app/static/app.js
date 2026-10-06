// the viewer: one book at a time, one set selected, the page it sits on with its boxes
const state = { books: [], book: null, page: 1, set: null, comp: null };
const $ = (id) => document.getElementById(id);
const api = (path, opts) => fetch("/api" + path, opts).then(async (r) => { if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json(); });

// fill the book dropdown and open the first one that has run
async function loadBooks() {
  state.books = await api("/books");
  const sel = $("book-select");
  sel.innerHTML = state.books.map((b) => `<option value="${b.id}">${b.project} / ${b.file}${b.status === "not run" ? (b.has_spec ? "" : " (needs API key)") : ` (${b.sets} sets)`}</option>`).join("");
  sel.onchange = () => openBook(sel.value);
  const first = state.books.find((b) => b.status !== "not run") || state.books[0];
  if (first) { sel.value = first.id; openBook(first.id); }
}

// fetch a book's result, select a set, and render everything
async function openBook(id, keepSet) {
  $("headline").textContent = "Extracting…";
  try {
    state.book = await api("/books/" + id);
  } catch (e) {
    $("headline").textContent = e.message; return;
  }
  const b = state.book, n = b.sets.length;
  $("pill").textContent = `${b.status.replace("_", " ").toUpperCase()} · ${b.page_count} PAGES`;
  $("headline").textContent = n ? `We pulled ${n} hardware sets from ${b.file}.` : `No hardware sets found in ${b.file}.`;
  $("export").href = `/api/books/${id}/export`;
  renderFlags(); renderSteps(); renderSets();
  const keep = keepSet && b.sets.find((s) => s.set_number === keepSet);
  selectSet(keep || b.sets[0] || null);
  try { $("spec-text").value = JSON.stringify(await api(`/books/${id}/spec`), null, 1); } catch (e) { $("spec-text").value = ""; }
}

function renderFlags() {
  const f = state.book.flags || [], box = $("flags");
  box.hidden = !f.length;
  box.innerHTML = `<b>&#9888; Audit flags (${f.length})</b>` + f.map((x) => `<div>${x.check}: ${x.count}${x.examples ? " · " + JSON.stringify(x.examples[0]).slice(0, 120) : ""}</div>`).join("");
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
  const ul = $("set-list"), sets = state.book.sets;
  $("sets-title").textContent = `Sets (${sets.length})`;
  ul.innerHTML = sets.map((s) => `<li data-n="${s.set_number}"><span>Set ${s.set_number}${s.status !== "active" ? ` <span class="muted">${s.status}</span>` : ""}</span><span class="muted">${s.components.length} · p${s.location[0]?.page ?? "?"}</span></li>`).join("");
  ul.querySelectorAll("li").forEach((li) => (li.onclick = () => selectSet(sets.find((s) => s.set_number === li.dataset.n))));
}

// jump to the set's first page and show its rows
function selectSet(s) {
  state.set = s; state.comp = null;
  $("set-list").querySelectorAll("li").forEach((li) => li.classList.toggle("active", !!s && li.dataset.n === s.set_number));
  if (!s) { $("set-title").textContent = "Hardware Set"; $("set-count").textContent = ""; $("comp-table").tBodies[0].innerHTML = ""; drawPage(1); return; }
  $("set-title").textContent = `Hardware Set ${s.set_number}${s.description ? " · " + s.description : ""}`;
  $("set-count").textContent = `${s.components.length} components`;
  $("set-status").textContent = s.status === "moved" ? `moved to ${s.moved_to}` : s.status === "not_used" ? "not used" : "";
  $("set-dot").className = "dot " + s.status;
  // the header block holds door numbers and lines like "Provide each PR door(s) with the following:"
  const doors = s.doors.filter((d) => !/provide|following|each|opening|description/i.test(d));
  $("doors-title").textContent = `Doors (${doors.length})`;
  $("doors").innerHTML = doors.map((d) => `<span>${d}</span>`).join("");
  $("set-notes").textContent = s.doors.filter((d) => !doors.includes(d)).concat(s.notes).join("\n");
  renderComponents(s);
  drawPage(s.location[0]?.page || 1);
  const li = $("set-list").querySelector("li.active"); if (li) li.scrollIntoView({ block: "nearest" });
}

// the component table. a cell is editable in place, a row click highlights its box on the page
function renderComponents(s) {
  const fields = ["qty", "description", "finish", "catalog_number", "mfr", "notes"];
  const cls = { qty: "qty", catalog_number: "catalog", mfr: "mfr", notes: "notes" };
  $("comp-table").tBodies[0].innerHTML = s.components.map((c, i) => `<tr data-i="${i}">` + fields.map((f) => {
    const v = c[f], corrected = (c.corrected || []).includes(f);
    return `<td class="${cls[f] || ""}${v == null ? " empty" : ""}${corrected ? " corrected" : ""}" data-f="${f}">${v == null ? "—" : v}</td>`;
  }).join("") + "</tr>").join("");
  $("comp-table").querySelectorAll("tr").forEach((tr) => {
    tr.onclick = () => selectComponent(s.components[+tr.dataset.i], tr);
    // single click selects the row, double click edits the cell, enter or leaving the cell saves
    tr.querySelectorAll("td").forEach((td) => {
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
  $("page-title").textContent = `Door Hardware Specs (Page ${state.page})`;
  const img = $("page-img"), wrap = $("page-wrap");
  wrap.querySelectorAll(".box").forEach((x) => x.remove());
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
  };
  img.src = `/api/books/${b.id}/pages/${state.page}.png`;
  if (img.complete) img.onload();
}

// the spec editor: save, rerun the book, keep the selected set
async function saveSpec() {
  const btn = $("save-spec"), msg = $("spec-msg");
  let spec;
  try { spec = JSON.parse($("spec-text").value); } catch (e) { msg.textContent = "not valid JSON: " + e.message; return; }
  btn.disabled = true; msg.textContent = "rerunning the book…";
  try {
    const keep = state.set && state.set.set_number;
    await api(`/books/${state.book.id}/spec`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(spec) });
    await openBook(state.book.id, keep);
    msg.textContent = "done";
  } catch (e) { msg.textContent = e.message; }
  btn.disabled = false;
}

function stepSet(d) {
  const sets = state.book.sets, i = sets.indexOf(state.set);
  if (sets[i + d]) selectSet(sets[i + d]);
}

$("save-spec").onclick = saveSpec;
$("prev-set").onclick = () => stepSet(-1);
$("next-set").onclick = () => stepSet(1);
$("prev-page").onclick = () => drawPage(state.page - 1);
$("next-page").onclick = () => drawPage(state.page + 1);
window.addEventListener("resize", () => drawPage(state.page));
loadBooks();
