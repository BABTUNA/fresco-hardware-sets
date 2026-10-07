# record the demo in docs/DEMO.md as a video: headless chromium drives the viewer, the narration is burned in
# as captions, a fake cursor shows the clicks. the viewer must be running on :8000 and scripts/demo_reset.sh run first
# usage: uv run python scripts/record_demo.py   writes out/demo/fresco-demo.mp4
import os, subprocess, time, glob
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "http://localhost:8000/"
OUT = os.path.join(ROOT, "out", "demo")
PDF = os.path.join(OUT, "Valor Acres - Door Hardware.pdf")
W, H = 1440, 900

# the caption bar and the cursor live in the page, re-added on every load
OVERLAY = """
(() => {
  // the init script runs before the body exists, so the overlay waits for it
  const init = () => {
  const css = document.createElement('style');
  css.textContent = `
    #demo-cap { position: fixed; left: 50%; bottom: 28px; transform: translateX(-50%); max-width: 1100px; z-index: 9999;
      background: rgba(17,24,39,.92); color: #fff; font: 500 20px/1.4 Inter, system-ui, sans-serif; padding: 12px 22px;
      border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,.25); transition: opacity .25s; pointer-events: none; }
    #demo-cap:empty { opacity: 0; }
    #demo-cur { position: fixed; z-index: 10000; width: 22px; height: 22px; pointer-events: none; transform: translate(-3px,-2px);
      transition: left .35s ease, top .35s ease; }
    #demo-cur.click::after { content: ""; position: absolute; left: -9px; top: -9px; width: 40px; height: 40px; border-radius: 50%;
      border: 3px solid #f59e0b; animation: demo-ring .5s ease-out forwards; }
    @keyframes demo-ring { from { transform: scale(.4); opacity: 1 } to { transform: scale(1.3); opacity: 0 } }`;
  document.head.appendChild(css);
  const cap = document.createElement('div'); cap.id = 'demo-cap'; document.body.appendChild(cap);
  const cur = document.createElement('div'); cur.id = 'demo-cur';
  cur.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 2l16 9-7 1.5L9 20z" fill="#111827" stroke="#fff" stroke-width="1.5"/></svg>';
  cur.style.left = '700px'; cur.style.top = '450px'; document.body.appendChild(cur);
  };
  if (document.body) init(); else document.addEventListener('DOMContentLoaded', init);
})();
"""


class Demo:
    def __init__(self, page):
        self.page = page

    # show a caption for about the time it takes to read it
    def say(self, text, hold=None):
        self.page.evaluate("t => { document.getElementById('demo-cap').textContent = t; }", text)
        time.sleep(hold if hold is not None else max(2.5, len(text.split()) / 2.6))

    def quiet(self):
        self.page.evaluate("document.getElementById('demo-cap').textContent = ''")

    def move(self, x, y):
        self.page.evaluate("([x, y]) => { const c = document.getElementById('demo-cur'); c.style.left = x + 'px'; c.style.top = y + 'px'; }", [x, y])
        self.page.mouse.move(x, y)
        time.sleep(0.45)

    def center(self, selector):
        box = self.page.locator(selector).first.bounding_box()
        return box["x"] + box["width"] / 2, box["y"] + min(box["height"] / 2, 18)

    def click(self, selector, double=False):
        self.page.locator(selector).first.scroll_into_view_if_needed()
        x, y = self.center(selector)
        self.move(x, y)
        self.page.evaluate("() => { const c = document.getElementById('demo-cur'); c.classList.remove('click'); void c.offsetWidth; c.classList.add('click'); }")
        if double:
            self.page.mouse.dblclick(x, y)
        else:
            self.page.mouse.click(x, y)
        time.sleep(0.6)

    def open_book(self, query, row_text):
        self.click("#books-btn") if self.page.locator("#books-btn").is_visible() else None
        self.page.fill("#book-search", "")
        self.click("#book-search")
        self.page.type("#book-search", query, delay=60)
        time.sleep(0.8)
        self.click(f"#book-table tbody tr:has-text('{row_text}')")
        self.page.wait_for_function("() => !document.getElementById('card').hidden && /We pulled/.test(document.getElementById('headline').textContent)", timeout=120000)
        time.sleep(1.5)

    def goto_page(self, n):
        self.click("#page-input")
        self.page.fill("#page-input", str(n))
        self.page.keyboard.press("Enter")
        time.sleep(1.5)

    def pick_set(self, num):
        self.click("#set-select")
        self.page.select_option("#set-select", num)
        time.sleep(1.5)


def run():
    os.makedirs(os.path.join(OUT, "video"), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=os.path.join(OUT, "video"), record_video_size={"width": W, "height": H}, device_scale_factor=1)
        page = ctx.new_page()
        page.add_init_script(OVERLAY)
        page.goto(URL)
        page.wait_for_selector("#book-table tbody tr")
        d = Demo(page)
        time.sleep(1)

        # the idea
        d.say("Every specbook uses one layout for all of its hardware sets.")
        d.say("So instead of sending every page to a model, a model reads two schedule pages once and writes a short layout spec for the book. Plain code then reads every page with it.")
        d.say("One call per book, deterministic after that, and every value comes from real words on the page, with a bounding box.")

        # an unseen book
        d.say("First, a PDF the system has never seen. Drop it on the library.")
        d.move(*d.center("#drop"))
        page.set_input_files("#file-input", PDF)
        d.say("It finds the schedule pages, one model call writes the layout spec, and the interpreter reads every page.", hold=4)
        page.wait_for_function("() => !document.getElementById('card').hidden && /We pulled/.test(document.getElementById('headline').textContent)", timeout=180000)
        time.sleep(1.5)
        d.say("37 sets, in about twenty seconds. Click a row and it lights up on the page: the box is where the value came from.", hold=2)
        d.click("#comp-table tbody tr:nth-child(3)")
        time.sleep(3)
        d.quiet()

        # livelle: columns, mfr vs finish, caveats
        d.open_book("livelle", "Vol1_rev1")
        d.say("Example one. A 1,191-page project manual. 58 of those pages hold sets, in a dealer format: Set 1.0, quantity, description, catalog, finish, maker.")
        d.click("#comp-table tbody tr:has-text('Cush Stop')")
        d.say("Here is the caveat from the brief. This NO could be Norton or the word No. The PE two rows down could be Pemko or painted enamel.")
        d.say("We never decide that from the value. The spec says the column at this x is the manufacturer column, so every code in it is a maker, for all 1,304 rows in the book. Zero finish and maker swaps on the benchmark.")
        d.pick_set("4.0")
        d.say("Sets run across page breaks. This one starts on page 644 and its last rows are on 645.", hold=2.5)
        d.click("#comp-table tbody tr:last-child")
        time.sleep(1.5)
        d.click("#next-page")
        d.say("Same set, a box on each page.", hold=3)
        d.move(*d.center("#comp-table thead th.conf"))
        d.say("Every row carries a confidence: its weakest field, from whether the value looks like its column, whether the column snapped to this page, and whether the row had a quantity. Under 0.8 is amber.")
        d.quiet()

        # gerrard: legend, confidence, corrections, column guides
        d.open_book("Hdw Spec", "Hdw Spec")
        d.say("Example two, a different book: a hardware dealer's own schedule. Set #AL 01, the doors listed under the header, 35 sets on 36 pages. Same code, a different spec.")
        d.move(*d.center("#pill"))
        d.say("This book prints a legend before its sets, and the extractor reads it.", hold=3)
        d.move(*d.center("#comp-table tbody tr:first-child td.mfr"))
        d.say("So HA is Hager Companies, CLR is Clear Anodized, and an option code inside a catalog number, like LAR, is Length as Required. No hardcoded dictionary. It comes off the page.")
        d.pick_set("24")
        d.move(*d.center("#comp-table tbody tr:has-text('Battery Backup') td.conf"))
        d.say("Here the confidence does its job. The finish cell on Battery Backup reads No, and the score flags it in red.")
        d.say("Fix one value: double-click, type, Enter. It is kept in a corrections file and survives every rerun.", hold=2)
        d.click("#comp-table tbody tr:has-text('Battery Backup') td[data-f='finish']", double=True)
        page.keyboard.type("No Finish", delay=70)
        page.keyboard.press("Enter")
        time.sleep(2.5)
        d.click("#guides-btn")
        d.say("For a mistake that hits every row, nobody edits a regex. The columns are lines on the page. Drag one and apply, and the whole book is re-read, with no model call.")
        d.click("#guides-cancel")
        d.quiet()

        # star: tag a line
        d.open_book("star", "Commons_Lane")
        d.goto_page(107)
        d.say("Star writes some headers as Hardware Group slash Sets. The model's spec missed this one, so set 102.1 was swallowed into set 102.")
        d.click("#lines-btn")
        d.say("Click the line, say what it is.", hold=1.5)
        d.click(".line[title*='102.1']")
        time.sleep(0.8)
        d.click("#line-menu button[data-kind='header']")
        page.wait_for_function("() => /Done/.test(document.getElementById('fix-msg').textContent)", timeout=120000)
        time.sleep(1.5)
        d.say("That became a literal rule in the spec and the book reran. There it is: set 102.1, fifteen rows.")
        d.move(*d.center("#feedback-note"))
        d.say("When a click is not enough, the box below takes a sentence instead, like: the set on this page is missing. One model call edits the layout and reruns.")
        d.quiet()

        # the numbers
        d.click("#books-btn")
        page.fill("#book-search", "")
        page.evaluate("renderLibrary()")
        d.move(700, 450)
        d.say("On 155 labeled pages from 20 books, scored strictly with every field exact: 98.5 percent of rows, and 94.9 percent of sets fully correct.")
        d.say("On a held-out set scored once after all tuning, 97.2 percent of rows. Across all 20 books, 1,174 of the 1,175 printed set numbers come out.")
        d.say("Code, the compiled specs, the labels and the benchmark are all in the repo.")
        d.quiet()
        time.sleep(1)
        ctx.close()
        browser.close()
    webm = max(glob.glob(os.path.join(OUT, "video", "*.webm")), key=os.path.getmtime)
    mp4 = os.path.join(OUT, "fresco-demo.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-r", "30", mp4], check=True)
    print("wrote", mp4)


if __name__ == "__main__":
    run()
